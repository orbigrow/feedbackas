# feedbackas/services/risk_service.py
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Count
from feedbackas.models import WellbeingCheckin, Feedback


def evaluate_burnout_flags_from_checkins(checkins):
    """
    Apskaičiuoja raudoną ir geltoną vėliavas iš pateikto anketų sąrašo (surūšiuoto nuo naujausio).
    
    Raudona vėliava (Aukšta rizika):
    Jei exhaustion_level <= 2 IR engagement_meaning <= 2 kartojasi bent 2 apklausas iš eilės.
    Tai tiesioginis signalas, kad darbuotojas nebėra tiesiog „pavargęs po sunkios savaitės“,
    o atsiriboja nuo darbo ir nebeatsigauna.
    
    Geltona vėliava (Vidutinė rizika):
    Jei workload_control <= 2 laikosi ilgiau nei 2 savaites, net jei kiti du rodikliai
    dar nepasiekė dugno (prevencija prieš atsirandant išsekimui).
    """
    if not checkins:
        return {
            'is_red_flag': False,
            'red_flag_reason': '',
            'is_yellow_flag': False,
            'yellow_flag_reason': '',
            'flag_level': 'none',
        }

    is_red_flag = False
    red_flag_reason = ''
    is_yellow_flag = False
    yellow_flag_reason = ''

    # 1. Raudona vėliava (Aukšta rizika):
    # exhaustion_level <= 2 IR engagement_meaning <= 2 kartojasi bent 2 apklausas iš eilės
    if len(checkins) >= 2:
        c0 = checkins[0]
        c1 = checkins[1]
        c0_danger = (getattr(c0, 'exhaustion_level', 3) <= 2 and getattr(c0, 'engagement_meaning', 3) <= 2)
        c1_danger = (getattr(c1, 'exhaustion_level', 3) <= 2 and getattr(c1, 'engagement_meaning', 3) <= 2)
        if c0_danger and c1_danger:
            is_red_flag = True
            red_flag_reason = 'Išsekimas ir atsiribojimas (<=2) kartojasi bent 2 apklausas iš eilės'

    # 2. Geltona vėliava (Vidutinė rizika):
    # workload_control <= 2 laikosi ilgiau nei 2 savaites
    if len(checkins) >= 2 and getattr(checkins[0], 'workload_control', 3) <= 2:
        consecutive_low = []
        for c in checkins:
            if getattr(c, 'workload_control', 3) <= 2:
                consecutive_low.append(c)
            else:
                break

        if len(consecutive_low) >= 2:
            span_days = (consecutive_low[0].created_at - consecutive_low[-1].created_at).total_seconds() / 86400.0
            if span_days >= 13.5:
                is_yellow_flag = True
                yellow_flag_reason = f'Perkrautas darbo krūvis / kontrolės trūkumas laikosi ilgiau nei 2 savaites ({int(span_days)} d.)'

    flag_level = 'critical' if is_red_flag else ('warning' if is_yellow_flag else 'none')

    return {
        'is_red_flag': is_red_flag,
        'red_flag_reason': red_flag_reason,
        'is_yellow_flag': is_yellow_flag,
        'yellow_flag_reason': yellow_flag_reason,
        'flag_level': flag_level,
    }


def evaluate_burnout_flags_for_user(user_id, company=None):
    """
    Įvertina individualaus darbuotojo perdegimo rizikos vėliavas pagal jo naujausias anketas.
    """
    qs = WellbeingCheckin.objects.filter(user_id=user_id)
    if company:
        qs = qs.filter(company=company)
    checkins = list(qs.order_by('-created_at')[:10])
    return evaluate_burnout_flags_from_checkins(checkins)


def calculate_team_risk_metrics(department_id=None, days=14):
    """
    Apskaičiuoja apibendrintą komandos perdegimo (Burnout) ir 
    išėjimo (Flight) riziką, garantuojant anonimiškumą (kvorumas >= 5).
    Vertinant perdegimą, balai nėra tiesiog suvidurkinami – atsižvelgiama į Raudonas ir Geltonas vėliavas.
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    
    entries = WellbeingCheckin.objects.filter(created_at__gte=cutoff_date)
    if department_id:
        entries = entries.filter(user__profile__department_id=department_id)
        
    unique_user_ids = list(entries.values_list('user_id', flat=True).distinct())
    unique_users = len(unique_user_ids)
    has_manager_entries = entries.filter(visibility='manager').exists()

    # Kvorumas taikomas anoniminiams įrašams; jei vartotojas nurodo, kad anketa vadovui, vadovas ją mato bet kuriuo atveju
    if unique_users < 5 and not has_manager_entries:
        return {'status': 'insufficient_quorum', 'message': 'Mažiau nei 5 nariai - duomenys slepiami dėl anonimiškumo.'}
        
    stats = entries.aggregate(
        avg_exhaustion=Avg('exhaustion_level'),       # 1 - 5
        avg_engagement=Avg('engagement_meaning'),     # 1 - 5
        avg_workload_ctrl=Avg('workload_control'),    # 1 - 5
        avg_mood=Avg('mood_score'),                  # 1 - 5
        avg_energy=Avg('energy_level'),              # 1 - 10
        avg_stress=Avg('stress_level'),              # 1 - 10
        avg_workload=Avg('workload_level'),          # 1 - 5
    )
    
    # Tikriname komandos narių Raudonas ir Geltonas vėliavas
    red_flags_count = 0
    yellow_flags_count = 0
    for uid in unique_user_ids:
        flags = evaluate_burnout_flags_for_user(uid)
        if flags['is_red_flag']:
            red_flags_count += 1
        elif flags['is_yellow_flag']:
            yellow_flags_count += 1

    # 1. Perdegimo indeksas (0 - 100):
    # Didelis stresas + didelis darbo krūvis + maža energija
    avg_stress = stats['avg_stress'] if stats['avg_stress'] is not None else 5.0
    avg_workload = stats['avg_workload'] if stats['avg_workload'] is not None else 3.0
    avg_energy = stats['avg_energy'] if stats['avg_energy'] is not None else 5.0
    avg_mood = stats['avg_mood'] if stats['avg_mood'] is not None else 3.0

    stress_factor = (avg_stress / 10.0) * 40.0
    workload_factor = (avg_workload / 5.0) * 35.0
    energy_deficit = ((10.0 - avg_energy) / 10.0) * 25.0
    base_burnout = stress_factor + workload_factor + energy_deficit

    # Integruojame vėliavas: jei yra darbuotojų su raudonomis/geltonomis vėliavomis, indeksas adekvačiai kyla
    if red_flags_count > 0:
        burnout_index = max(base_burnout, 75.0 + min(20.0, red_flags_count * 5.0))
    elif yellow_flags_count > 0:
        burnout_index = max(base_burnout, 55.0 + min(15.0, yellow_flags_count * 3.0))
    else:
        burnout_index = base_burnout

    burnout_index = round(min(100.0, max(0.0, burnout_index)), 1)
    
    # 2. Išėjimo rizika (Flight Risk 0 - 100%):
    mood_deficit = ((5.0 - avg_mood) / 5.0) * 45.0
    flight_risk = round(mood_deficit + (burnout_index * 0.55), 1)
    flight_risk = round(min(100.0, max(0.0, flight_risk)), 1)
    
    return {
        'status': 'success',
        'burnout_index': burnout_index,
        'flight_risk': flight_risk,
        'stats': stats,
        'unique_contributors': unique_users,
        'red_flags_count': red_flags_count,
        'yellow_flags_count': yellow_flags_count,
        'requires_action': burnout_index > 65 or flight_risk > 50 or red_flags_count > 0,
    }


def can_view_manager_survey(viewer, survey):
    """
    Patikrina, ar vartotojas (viewer) turi teisę matyti kito darbuotojo/vadovo
    savijautos anketą, skirtą vadovui (visibility='manager').
    
    Taisyklės:
    1. Vartotojas niekada negali matyti savo paties anketos kaip vadovas.
    2. Supervartotojas mato visas įmonės anketas (išskyrus savo paties).
    3. Tiesioginis vadovas, priskirtas darbuotojo profilyje (profile.manager), mato anketą.
    4. Jei anketą užpildė skyriaus vadovas:
       - Ją mato TIK jo vadovas (t.y. tėvinio skyriaus vadovas arba aukštesni tėviniai vadovai)
         arba tiesioginis vadovas profilyje, arba įmonės administratorius.
       - Pavaldiniai tame pačiame skyriuje ar poskyriuose jos nematys.
    5. Jei anketą užpildė paprastas skyriaus darbuotojas:
       - Ją mato jo skyriaus vadovas, tėvinių skyrių vadovai ir įmonės administratorius.
    """
    if not viewer or not getattr(viewer, 'is_authenticated', False):
        return False

    # 1. Niekas negali matyti savo paties užpildytos anketos kaip vadovas
    if survey.user_id == viewer.id:
        return False

    # 2. Supervartotojas
    if getattr(viewer, 'is_superuser', False):
        return True

    survey_user = survey.user
    survey_user_profile = getattr(survey_user, 'profile', None)
    viewer_profile = getattr(viewer, 'profile', None)

    # Įmonės atitikimas
    survey_company_id = survey.company_id or (getattr(survey_user_profile, 'company_link_id', None) if survey_user_profile else None)
    viewer_company_id = getattr(viewer_profile, 'company_link_id', None) if viewer_profile else None
    if survey_company_id and viewer_company_id and survey_company_id != viewer_company_id:
        return False

    # 3. Tiesioginis vadovas (priskirtas profilyje)
    if survey_user_profile and survey_user_profile.manager_id == viewer.id:
        return True

    # 4. Nustatome anketos vartotojo skyrių
    user_dept = getattr(survey, 'department', None) or (getattr(survey_user_profile, 'department', None) if survey_user_profile else None)

    # 5. Jei anketos autorius yra skyriaus vadovas:
    if user_dept and user_dept.manager_id == survey_user.id:
        # Skyriaus vadovo anketą gali matyti TIK jo vadovas hierarchijoje į viršų
        curr_parent = user_dept.parent
        while curr_parent:
            if curr_parent.manager_id == viewer.id:
                return True
            curr_parent = curr_parent.parent

        # Įmonės administratorius
        if viewer_profile and viewer_profile.is_company_admin:
            return True

        return False

    # 6. Jei anketos autorius yra paprastas skyriaus darbuotojas:
    if user_dept:
        if user_dept.manager_id == viewer.id:
            return True

        curr_parent = user_dept.parent
        while curr_parent:
            if curr_parent.manager_id == viewer.id:
                return True
            curr_parent = curr_parent.parent

    # 7. Įmonės administratorius (pvz. HR)
    if viewer_profile and viewer_profile.is_company_admin:
        return True

    return False


def build_hierarchical_departments(departments):
    """
    Surūšiuoja skyrių sąrašą pagal organizacinę medžio hierarchiją (DFS: Tėvinis -> Vaikiniai -> Poskyriai).
    Kiekvienam skyriui priskiria:
      - hierarchy_level (0, 1, 2...)
      - hierarchy_parent_name (tėvinio skyriaus pavadinimas)
      - hierarchy_path ("Generalinis / IT / Poskyris")
      - is_root_department (ar tai šakninis skyrius šiame sąraše)
      - has_sub_departments (ar turi vaikinių skyrių)
    """
    if not departments:
        return []

    dept_list = list(departments)
    dept_map = {d.id: d for d in dept_list}
    children_map = {d.id: [] for d in dept_list}
    roots = []

    for d in dept_list:
        if d.parent_id and d.parent_id in dept_map:
            children_map[d.parent_id].append(d)
        else:
            roots.append(d)

    roots.sort(key=lambda x: (x.name or '').lower())
    for p_id in children_map:
        children_map[p_id].sort(key=lambda x: (x.name or '').lower())

    ordered = []

    def dfs(dept, level=0, path=None):
        current_path = (path or []) + [dept.name]
        parent_obj = dept_map.get(dept.parent_id) if (dept.parent_id and dept.parent_id in dept_map) else None

        dept.hierarchy_level = level
        dept.hierarchy_parent_name = parent_obj.name if parent_obj else None
        dept.hierarchy_path = " / ".join(current_path)
        dept.is_root_department = (level == 0)
        dept.has_sub_departments = len(children_map.get(dept.id, [])) > 0

        ordered.append(dept)
        for child in children_map.get(dept.id, []):
            dfs(child, level + 1, current_path)

    for r in roots:
        dfs(r, 0, [])

    return ordered


