# feedbackas/services/burnout_signals.py
"""
Kolegų įvertinimuose slypinčių perdegimo signalų aptikimas ir AI analitika.

Analizuojami darbuotojo GAUTI atsiliepimai (Feedback, kur feedback_request.requester yra
vertinamasis): pažymėti raktiniai žodžiai ir laisvos formos komentarai. Jei signalų daugėja,
vadovas rizikos radare mato įspėjimą ir gali atsidaryti išsamią AI analizę.
"""
import hashlib
import logging
import unicodedata
from collections import Counter, OrderedDict
from datetime import timedelta
from types import SimpleNamespace

from django.utils import timezone

logger = logging.getLogger(__name__)

# Kiek dienų atgal analizuojami gauti įvertinimai
LOOKBACK_DAYS = 180

# Raktiniai žodžiai, kuriuos kolegos gali pažymėti debesyje, jei pastebi artėjantį perdegimą.
# SVARBU: šis sąrašas naudojamas ir fill_feedback.html raktinių žodžių debesyje (per template tag).
BURNOUT_CLOUD_KEYWORDS = [
    'Atrodo pavargęs',
    'Išsekęs',
    'Perkrautas darbais',
    'Dirba viršvalandžius',
    'Dirba savaitgaliais',
    'Neatsijungia po darbo',
    'Nuolatinis skubėjimas',
    'Nesuspėja su terminais',
    'Prarado entuziazmą',
    'Sumažėjęs įsitraukimas',
    'Atsiribojęs nuo komandos',
    'Irzlumas',
    'Cinizmas',
    'Sunkiai susikaupia',
    'Daugiau klaidų nei įprastai',
    'Nebeinicijuoja',
    'Emociškai išsekęs',
    'Neima atostogų',
    'Viską tempia vienas',
    'Reikia pagalbos',
]

# Silpnesni signalai iš esamo neigiamų žodžių sąrašo – patys savaime nereiškia perdegimo,
# bet kartu su kitais signalais stiprina vaizdą.
WEAK_SIGNAL_KEYWORDS = [
    'Stresas', 'Apatija', 'Abejingumas', 'Išsiblaškymas', 'Dėmesio stoka',
    'Pasyvumas', 'Lėtas darbas', 'Pesimizmas', 'Uždarumas', 'Negatyvumas',
]

# Komentarų šaknys (lyginama be diakritikų, mažosiomis raidėmis)
COMMENT_STEMS = [
    # LT
    'perdeg', 'pervarg', 'pavarg', 'nuovarg', 'išsek', 'išsunk', 'perkraut', 'perkrov',
    'viršvaland', 'savaitgaliais dirb', 'dirba savaitgal', 'dirba naktim', 'naktimis dirb',
    'vėlai vakar', 'neatsijung', 'nebespėj', 'nesuspėj', 'nespėja', 'stres', 'įtamp',
    'spaudim', 'irzl', 'užsisklend', 'atsiriboj', 'apati', 'cinizm', 'cinišk',
    'prarado motyvac', 'prarado entuziazm', 'prarado susidom', 'nebeturi energ',
    'neturi energ', 'nebėra energ', 'be energijos', 'neima atostog', 'nebeišsitemp',
    'viską tempia', 'per daug darb', 'per didel krūv', 'didelis krūv', 'perdaug darb',
    # EN
    'burnout', 'burned out', 'burnt out', 'exhaust', 'overwhelm', 'overwork', 'overtime',
    'tired', 'fatigue', 'stressed', 'overloaded', 'no energy', 'irritab', 'withdrawn', 'cynical',
]


def _normalize(text):
    """Mažosios raidės + diakritikų pašalinimas (ė→e, š→s ir t.t.)."""
    if not text:
        return ''
    text = unicodedata.normalize('NFKD', str(text).lower())
    return ''.join(ch for ch in text if not unicodedata.combining(ch))


_STRONG_NORM = {_normalize(k): k for k in BURNOUT_CLOUD_KEYWORDS}
_WEAK_NORM = {_normalize(k): k for k in WEAK_SIGNAL_KEYWORDS}
_STEMS_NORM = [(_normalize(s), s) for s in COMMENT_STEMS]


def scan_feedback(feedback):
    """
    Grąžina vieno atsiliepimo perdegimo signalus:
    {strong: [...], weak: [...], comment_hits: [...], score: float, is_flagged: bool}
    """
    raw_keywords = [k.strip() for k in (feedback.keywords or '').split(',') if k.strip()]
    strong, weak = [], []
    for kw in raw_keywords:
        n = _normalize(kw)
        if n in _STRONG_NORM:
            strong.append(_STRONG_NORM[n])
        elif n in _WEAK_NORM:
            weak.append(_WEAK_NORM[n])
        else:
            # Laisvai įvesti žodžiai (ne iš debesies) – tikriname pagal šaknis
            if any(stem in n for stem, _ in _STEMS_NORM):
                strong.append(kw)

    comment_norm = _normalize(feedback.comments)
    comment_hits = [orig for stem, orig in _STEMS_NORM if stem and stem in comment_norm]

    score = len(strong) + 0.5 * len(weak) + (1.0 if comment_hits else 0.0)
    is_flagged = bool(strong) or bool(comment_hits) or len(weak) >= 2

    return {
        'keywords': raw_keywords,
        'strong': strong,
        'weak': weak,
        'comment_hits': comment_hits,
        'score': score,
        'is_flagged': is_flagged,
    }


def _determine_level(total, flagged, distinct_recent_evaluators):
    if flagged == 0:
        return 'none'
    ratio = flagged / total if total else 0
    if (flagged >= 3 and ratio >= 0.4) or distinct_recent_evaluators >= 3:
        return 'high'
    if flagged >= 2 or ratio >= 0.3:
        return 'medium'
    return 'low'


def _get_feedbacks_for_users(user_ids, lookback_days=LOOKBACK_DAYS):
    from feedbackas.models import Feedback
    since = timezone.now() - timedelta(days=lookback_days)
    return list(
        Feedback.objects.filter(
            feedback_request__requester_id__in=list(user_ids),
            created_at__gte=since,
        ).select_related('feedback_request').order_by('-created_at')
    )


def summarize_feedbacks(feedbacks, lookback_days=LOOKBACK_DAYS):
    """Sukuria lengvą signalų santrauką lentelei (be AI)."""
    now = timezone.now()
    recent_cutoff = now - timedelta(days=60)
    total = len(feedbacks)
    flagged = 0
    distinct_recent = set()
    for fb in feedbacks:
        scan = scan_feedback(fb)
        if scan['is_flagged']:
            flagged += 1
            if fb.created_at >= recent_cutoff:
                distinct_recent.add(fb.feedback_request.requested_to_id)
    level = _determine_level(total, flagged, len(distinct_recent))
    return {
        'total': total,
        'flagged': flagged,
        'ratio_pct': int(round(100 * flagged / total)) if total else 0,
        'level': level,
        'needs_attention': level in ('medium', 'high'),
    }


def summarize_for_users(user_ids, lookback_days=LOOKBACK_DAYS):
    """Grąžina {user_id: summary} visiems nurodytiems darbuotojams vienu DB užklausimu."""
    grouped = {uid: [] for uid in user_ids}
    for fb in _get_feedbacks_for_users(user_ids, lookback_days):
        grouped.setdefault(fb.feedback_request.requester_id, []).append(fb)
    return {uid: summarize_feedbacks(fbs, lookback_days) for uid, fbs in grouped.items()}


def build_employee_signal_report(employee, lookback_days=LOOKBACK_DAYS):
    """
    Išsami vieno darbuotojo signalų ataskaita (naudojama modale ir AI analizei).
    Vertintojų vardai NĖRA įtraukiami – tik anoniminiai identifikatoriai.
    """
    now = timezone.now()
    feedbacks = _get_feedbacks_for_users([employee.id], lookback_days)
    total = len(feedbacks)

    # Mėnesinė laiko juosta (nuo seniausio iki naujausio)
    months = OrderedDict()
    for i in range(5, -1, -1):
        y, m = now.year, now.month - i
        while m <= 0:
            m += 12
            y -= 1
        key = f'{y:04d}-{m:02d}'
        months[key] = {'label': key, 'total': 0, 'flagged': 0}

    strong_counter, weak_counter, stem_counter = Counter(), Counter(), Counter()
    flagged_items = []
    evaluator_alias = {}
    recent_cutoff = now - timedelta(days=60)
    half_cutoff = now - timedelta(days=lookback_days // 2)
    distinct_recent = set()
    recent_total = recent_flagged = older_total = older_flagged = 0
    recent_ratings, older_ratings = [], []

    for fb in feedbacks:
        scan = scan_feedback(fb)
        key = fb.created_at.strftime('%Y-%m')
        if key in months:
            months[key]['total'] += 1
            if scan['is_flagged']:
                months[key]['flagged'] += 1

        is_recent_half = fb.created_at >= half_cutoff
        if is_recent_half:
            recent_total += 1
            recent_flagged += 1 if scan['is_flagged'] else 0
            if fb.rating:
                recent_ratings.append(fb.rating)
        else:
            older_total += 1
            older_flagged += 1 if scan['is_flagged'] else 0
            if fb.rating:
                older_ratings.append(fb.rating)

        if not scan['is_flagged']:
            continue

        evaluator_id = fb.feedback_request.requested_to_id
        if evaluator_id not in evaluator_alias:
            evaluator_alias[evaluator_id] = f'K{len(evaluator_alias) + 1}'
        if fb.created_at >= recent_cutoff:
            distinct_recent.add(evaluator_id)

        strong_counter.update(scan['strong'])
        weak_counter.update(scan['weak'])
        stem_counter.update(scan['comment_hits'])

        comment = (fb.comments or '').strip()
        flagged_items.append({
            'date': fb.created_at.strftime('%Y-%m-%d'),
            'evaluator': evaluator_alias[evaluator_id],
            'signal_keywords': scan['strong'] + scan['weak'],
            'all_keywords': scan['keywords'],
            'comment_excerpt': (comment[:400] + '…') if len(comment) > 400 else comment,
            'has_comment_signal': bool(scan['comment_hits']),
        })

    flagged = len(flagged_items)
    level = _determine_level(total, flagged, len(distinct_recent))

    recent_ratio = recent_flagged / recent_total if recent_total else 0
    older_ratio = older_flagged / older_total if older_total else 0
    if recent_total and older_total:
        if recent_ratio - older_ratio >= 0.15:
            trend = 'worsening'
        elif older_ratio - recent_ratio >= 0.15:
            trend = 'improving'
        else:
            trend = 'stable'
    else:
        trend = 'worsening' if recent_flagged >= 2 else 'stable'

    def _avg(values):
        return round(sum(values) / len(values), 2) if values else None

    top_keywords = [
        {'keyword': k, 'count': c, 'strength': 'strong'} for k, c in strong_counter.most_common(8)
    ] + [
        {'keyword': k, 'count': c, 'strength': 'weak'} for k, c in weak_counter.most_common(4)
    ]

    return {
        'lookback_days': lookback_days,
        'total_feedbacks': total,
        'flagged_feedbacks': flagged,
        'flagged_ratio_pct': int(round(100 * flagged / total)) if total else 0,
        'distinct_evaluators_flagging': len(evaluator_alias),
        'distinct_recent_evaluators': len(distinct_recent),
        'level': level,
        'trend': trend,
        'recent_flagged_ratio_pct': int(round(100 * recent_ratio)),
        'older_flagged_ratio_pct': int(round(100 * older_ratio)),
        'avg_rating_recent': _avg(recent_ratings),
        'avg_rating_older': _avg(older_ratings),
        'timeline': list(months.values()),
        'top_keywords': top_keywords,
        'comment_signal_terms': [k for k, _ in stem_counter.most_common(8)],
        'flagged_items': flagged_items[:25],
        'fingerprint': _fingerprint(feedbacks, lookback_days),
    }


def _fingerprint(feedbacks, lookback_days):
    max_id = max((fb.id for fb in feedbacks), default=0)
    raw = f'{len(feedbacks)}:{max_id}:{lookback_days}:v1'
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


def can_view_employee_signals(viewer, employee):
    """
    Prieigos kontrolė perdegimo signalų analizei:
    1. Vartotojas (viewer) visada gali matyti savo paties gautų įvertinimų analizę.
    2. Superadministratorius mato visus darbuotojus.
    3. Įmonės administratorius (is_company_admin) mato visus savo įmonės darbuotojus.
    4. Tiesioginis vadovas (profilyje priskirtas manager) mato pavaldinius.
    5. Skyriaus vadovas mato savo skyriaus ir pavaldžių poskyrių darbuotojus.
    """
    if not viewer or not getattr(viewer, 'is_authenticated', False):
        return False

    # 1. Darbuotojas / vadovas visada gali matyti savo paties analizę
    if viewer.id == employee.id:
        return True

    # 2. Superadministratorius
    if getattr(viewer, 'is_superuser', False):
        return True

    viewer_profile = getattr(viewer, 'profile', None)
    emp_profile = getattr(employee, 'profile', None)

    # 3. Įmonės atitikimas
    v_cid = getattr(viewer_profile, 'company_link_id', None) if viewer_profile else None
    e_cid = getattr(emp_profile, 'company_link_id', None) if emp_profile else None
    if v_cid and e_cid and v_cid != e_cid:
        return False

    # 4. Įmonės administratorius (pvz. HR)
    if viewer_profile and viewer_profile.is_company_admin:
        return True

    # 5. Tiesioginis vadovas profilyje
    if emp_profile and emp_profile.manager_id == viewer.id:
        return True

    # 6. Skyriaus vadovas (tiesioginis arba hierarchijoje į viršų)
    emp_dept = getattr(emp_profile, 'department', None) if emp_profile else None
    curr_dept = emp_dept
    while curr_dept:
        if curr_dept.manager_id == viewer.id:
            return True
        curr_dept = curr_dept.parent

    # 7. Vadovo valdomi skyriai (jei viewer yra bet kurio skyriaus vadovas įmonėje)
    try:
        from users.models import Department
        managed_dept_ids = set()
        to_check = list(Department.objects.filter(manager=viewer))
        while to_check:
            d = to_check.pop(0)
            managed_dept_ids.add(d.id)
            for child in Department.objects.filter(parent=d):
                if child.id not in managed_dept_ids:
                    to_check.append(child)
        if emp_dept and emp_dept.id in managed_dept_ids:
            return True
    except Exception:
        pass

    return False


# ---------------------------------------------------------------------------
# Analizės sudarymas (taisyklėmis grįstas atsarginis variantas + AI)
# ---------------------------------------------------------------------------

def build_rule_based_analysis(report, language='lt'):
    level = report['level']
    lt = language != 'en'
    level_to_score = {'none': 8, 'low': 30, 'medium': 55, 'high': 78}
    kw = ', '.join(k['keyword'] for k in report['top_keywords'][:4])

    if level == 'none':
        headline = 'Perdegimo signalų kolegų įvertinimuose nerasta' if lt else 'No burnout signals found in peer feedback'
        summary = (
            f"Per paskutines {report['lookback_days']} d. išanalizuota {report['total_feedbacks']} įvertinimų – "
            "nė viename nebuvo raktinių žodžių ar komentarų, rodančių išsekimą ar perkrovą."
            if lt else
            f"{report['total_feedbacks']} feedback entries from the last {report['lookback_days']} days were analysed – "
            "none contained keywords or comments indicating exhaustion or overload."
        )
        recs = (['Tęskite reguliarius 1-on-1 pokalbius ir stebėkite savijautos anketas.']
                if lt else ['Keep regular 1-on-1s and monitor well-being check-ins.'])
    else:
        headline = (
            f"{report['flagged_feedbacks']} iš {report['total_feedbacks']} įvertinimų turi perdegimo signalų"
            if lt else
            f"{report['flagged_feedbacks']} of {report['total_feedbacks']} feedback entries contain burnout signals"
        )
        summary = (
            f"Signalus pažymėjo {report['distinct_evaluators_flagging']} skirtingi kolegos. "
            f"Dažniausiai minima: {kw or 'komentaruose minimas nuovargis/krūvis'}."
            if lt else
            f"Signals were raised by {report['distinct_evaluators_flagging']} different colleagues. "
            f"Most frequent: {kw or 'fatigue/workload mentioned in comments'}."
        )
        recs = ([
            'Suplanuokite neformalų 1-on-1 pokalbį apie savijautą (ne apie rezultatus).',
            'Peržiūrėkite darbuotojo užduočių sąrašą ir terminus – ar galima ką nors perskirstyti.',
            'Įsitikinkite, kad darbuotojas turi galimybę pailsėti ir išnaudoti atostogas.',
        ] if lt else [
            'Schedule an informal 1-on-1 focused on well-being (not performance).',
            'Review workload and deadlines – identify what can be redistributed.',
            'Make sure the employee can rest and use their vacation days.',
        ])

    trajectory = report['trend']
    return {
        'risk_level': level if level != 'none' else 'low',
        'risk_score': level_to_score.get(level, 30),
        'trajectory': trajectory,
        'headline': headline,
        'summary': summary,
        'key_signals': [k['keyword'] for k in report['top_keywords'][:5]],
        'protective_factors': [],
        'recommendations': recs,
        'conversation_starters': ([
            'Kaip šiuo metu jautiesi dėl savo darbo krūvio?',
            'Kas pastaruoju metu atima daugiausiai energijos?',
            'Ką galėčiau padaryti, kad tau būtų lengviau?',
        ] if lt else [
            'How do you currently feel about your workload?',
            'What has been draining your energy lately?',
            'What could I do to make things easier for you?',
        ]) if level != 'none' else [],
    }


def get_or_build_analysis(employee, report, requested_by=None, language='lt', force=False):
    """
    Grąžina išsaugotą analizę pagal duomenų „pirštų atspaudą“ arba None (jei reikia AI).
    Jei signalų nėra – AI nekviečiamas, grąžinama taisyklėmis grįsta analizė.
    """
    from feedbackas.models import BurnoutSignalAnalysis
    fp = f"{report['fingerprint']}:{language}"
    if not force:
        existing = BurnoutSignalAnalysis.objects.filter(employee=employee, fingerprint=fp).first()
        if existing:
            return existing
    if report['flagged_feedbacks'] == 0:
        return BurnoutSignalAnalysis.objects.create(
            employee=employee,
            company=getattr(getattr(employee, 'profile', None), 'company_link', None),
            requested_by=requested_by,
            fingerprint=fp,
            risk_level='none',
            source='rules',
            result=build_rule_based_analysis(report, language),
        )
    return None


def run_burnout_ai_analysis_task(employee_id, requested_by_id=None, language='lt'):
    """django-q užduotis: atlieka AI analizę ir išsaugo rezultatą DB."""
    from django.contrib.auth.models import User
    from feedbackas.models import BurnoutSignalAnalysis
    from feedbackas.ai_service import OpenRouterService

    employee = User.objects.select_related('profile', 'profile__company_link').get(id=employee_id)
    requested_by = User.objects.filter(id=requested_by_id).select_related('profile', 'profile__company_link').first() if requested_by_id else None
    
    emp_profile = getattr(employee, 'profile', None)
    req_profile = getattr(requested_by, 'profile', None) if requested_by else None
    company = getattr(emp_profile, 'company_link', None) or (getattr(req_profile, 'company_link', None) if req_profile else None)
    user_for_log = requested_by or employee

    report = build_employee_signal_report(employee)
    fp = f"{report['fingerprint']}:{language}"

    source = 'ai'
    try:
        result = OpenRouterService.analyze_burnout_signals(
            report, language=language, user=user_for_log, company=company
        )
        if not result:
            raise ValueError('Empty AI result')
    except Exception as e:
        logger.error(f'Burnout AI analysis failed for user {employee_id}: {e}')
        result = build_rule_based_analysis(report, language)
        source = 'rules'


    obj = BurnoutSignalAnalysis.objects.create(
        employee=employee,
        company=company,
        requested_by=requested_by,
        fingerprint=fp,
        risk_level=result.get('risk_level', report['level']),
        source=source,
        result=result,
    )
    return obj.id
