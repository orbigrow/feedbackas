from django.utils.translation import gettext as _
from django.conf import settings
from django.db.models import Avg
from feedbackas.models import Feedback, FeedbackRequest
from django.contrib.auth.models import User
from .risk_service import calculate_team_risk_metrics, evaluate_burnout_flags_for_user

class FeedbackAnalytics:
    @staticmethod
    def get_user_stats(user, period='all'):
        """
        Apskaičiuoja vartotojo atsiliepimų statistiką ir kompetencijų vidurkius.
        """
        from django.utils import timezone
        import datetime
        
        filters = {
            'feedback_request__requester': user,
            'feedback_request__status': 'completed'
        }
        
        now = timezone.now()
        if period == 'month':
            filters['feedback_request__created_at__gte'] = now - datetime.timedelta(days=30)
        elif period == 'quarter':
            filters['feedback_request__created_at__gte'] = now - datetime.timedelta(days=90)
        elif period == 'year':
            filters['feedback_request__created_at__gte'] = now - datetime.timedelta(days=365)
            
        completed_feedback = Feedback.objects.filter(**filters)
        completed_feedback_count = completed_feedback.count()
        
        # Participation Rate
        total_requests_filters = {'requester': user}
        if period == 'month':
            total_requests_filters['created_at__gte'] = now - datetime.timedelta(days=30)
        elif period == 'quarter':
            total_requests_filters['created_at__gte'] = now - datetime.timedelta(days=90)
        elif period == 'year':
            total_requests_filters['created_at__gte'] = now - datetime.timedelta(days=365)
        
        total_requests = FeedbackRequest.objects.filter(**total_requests_filters).count()
        participation_rate = 0
        if total_requests > 0:
            participation_rate = int((completed_feedback_count / total_requests) * 100)
            
        overall_avg_rating = completed_feedback.aggregate(Avg('rating'))['rating__avg'] or 0
        
        # Top % In Company
        top_percentile = '--'
        if hasattr(user, 'profile') and user.profile.company_link:
            company = user.profile.company_link
            company_users = User.objects.filter(profile__company_link=company)
            
            user_scores = []
            for u in company_users:
                u_filters = {
                    'feedback_request__requester': u,
                    'feedback_request__status': 'completed'
                }
                if period == 'month':
                    u_filters['feedback_request__created_at__gte'] = now - datetime.timedelta(days=30)
                elif period == 'quarter':
                    u_filters['feedback_request__created_at__gte'] = now - datetime.timedelta(days=90)
                elif period == 'year':
                    u_filters['feedback_request__created_at__gte'] = now - datetime.timedelta(days=365)
                    
                u_avg = Feedback.objects.filter(**u_filters).aggregate(Avg('rating'))['rating__avg'] or 0
                if u_avg > 0:
                    user_scores.append(u_avg)
                    
            if user_scores and overall_avg_rating > 0:
                user_scores.sort(reverse=True)
                if overall_avg_rating in user_scores:
                    rank = user_scores.index(overall_avg_rating) + 1
                    percentile_calc = int((rank / len(user_scores)) * 100)
                    top_percentile = percentile_calc if percentile_calc > 0 else 1
        
        all_keywords = []
        all_strengths = []
        all_improvements = []
        
        for feedback in completed_feedback:
            keywords = [kw.strip() for kw in feedback.keywords.split(',') if kw.strip()]
            all_keywords.extend(keywords)
            
            # Sumuojame AI išskirtas savybes
            if isinstance(feedback.extracted_strengths, list):
                all_strengths.extend(feedback.extracted_strengths)
            if isinstance(feedback.extracted_improvements, list):
                all_improvements.extend(feedback.extracted_improvements)

        competency_averages = completed_feedback.aggregate(
            teamwork=Avg('teamwork_rating'),
            communication=Avg('communication_rating'),
            initiative=Avg('initiative_rating'),
            technical_skills=Avg('technical_skills_rating'),
            problem_solving=Avg('problem_solving_rating')
        )
        competencies = [
            {'name': _('Komandinis Darbas'), 'score': round(competency_averages.get('teamwork') or 0, 2)},
            {'name': _('Komunikacija'), 'score': round(competency_averages.get('communication') or 0, 2)},
            {'name': _('Iniciatyvumas'), 'score': round(competency_averages.get('initiative') or 0, 2)},
            {'name': _('Techninės Žinios'), 'score': round(competency_averages.get('technical_skills') or 0, 2)},
            {'name': _('Problemų Sprendimas'), 'score': round(competency_averages.get('problem_solving') or 0, 2)},
        ]

        training_map = {
            'Komandinis Darbas': 'Mokymai apie efektyvų komandinį darbą',
            'Komunikacija': 'Viešojo kalbėjimo ir komunikacijos įgūdžių mokymai',
            'Iniciatyvumas': 'Proaktyvumo ir iniciatyvumo skatinimo seminaras',
            'Techninės Žinios': 'Specializuoti techniniai kursai pagal Jūsų sritį',
            'Problemų Sprendimas': 'Kritinio mąstymo ir problemų sprendimo dirbtuvės',
        }
        
        recommended_trainings = []
        for competency in competencies:
            if competency['score'] < 7:
                recommended_trainings.append({
                    'competency': competency['name'],
                    'training': training_map.get(competency['name'], 'Bendrieji tobulinimosi kursai')
                })
        
        return {
            'overall_avg_rating': round(overall_avg_rating, 2),
            'received_feedback_count': completed_feedback_count,
            'participation_rate': participation_rate,
            'top_percentile': top_percentile,
            'all_keywords': list(set(all_keywords))[:7],
            'competencies': competencies,
            'strengths': all_strengths[:5],
            'improvements': all_improvements[:5],
            'recommended_trainings': recommended_trainings,
        }

def generate_ai_feedback_task(ratings, keywords, comments, existing_feedback, colleague_name, user_id=None, language='lt', colleague_first_name=None, colleague_last_name=None):
    from feedbackas.ai_service import OpenRouterService
    from django.contrib.auth.models import User
    
    user = None
    company = None
    if user_id:
        try:
            user = User.objects.get(id=user_id)
            if hasattr(user, 'profile') and user.profile.company_link:
                company = user.profile.company_link
        except User.DoesNotExist:
            pass

    return OpenRouterService.generate(
        ratings=ratings,
        keywords=keywords,
        comments=comments,
        existing_feedback=existing_feedback,
        colleague_name=colleague_name,
        user=user,
        company=company,
        language=language,
        colleague_first_name=colleague_first_name,
        colleague_last_name=colleague_last_name
    )

class TeamAnalytics:
    @staticmethod
    def get_team_stats(team_members):
        """
        Apskaičiuoja visos komandos statistiką.
        """
        from django.db.models import Avg, Count, Q
        
        # Per-member stats using annotation instead of N+1 queries
        annotated_members = team_members.annotate(
            avg_rating=Avg('made_requests__feedback__rating', filter=Q(made_requests__status='completed')),
            feedback_count=Count('made_requests__feedback', filter=Q(made_requests__status='completed'), distinct=True)
        )

        member_stats = []
        for member in annotated_members:
            member_stats.append({
                'user': member,
                'avg_rating': round(member.avg_rating, 2) if member.avg_rating else None,
                'feedback_count': member.feedback_count,
            })
        
        # Team-wide aggregated stats
        all_team_feedback = Feedback.objects.filter(
            feedback_request__requester__in=team_members,
            feedback_request__status='completed'
        )
        
        team_avg_rating = all_team_feedback.aggregate(Avg('rating'))['rating__avg'] or 0
        team_feedback_count = all_team_feedback.count()
        
        competency_averages = all_team_feedback.aggregate(
            teamwork=Avg('teamwork_rating'),
            communication=Avg('communication_rating'),
            initiative=Avg('initiative_rating'),
            technical_skills=Avg('technical_skills_rating'),
            problem_solving=Avg('problem_solving_rating')
        )
        
        competencies = [
            {'name': _('Komandinis Darbas'), 'score': round(competency_averages.get('teamwork') or 0, 2)},
            {'name': _('Komunikacija'), 'score': round(competency_averages.get('communication') or 0, 2)},
            {'name': _('Iniciatyvumas'), 'score': round(competency_averages.get('initiative') or 0, 2)},
            {'name': _('Techninės Žinios'), 'score': round(competency_averages.get('technical_skills') or 0, 2)},
            {'name': _('Problemų Sprendimas'), 'score': round(competency_averages.get('problem_solving') or 0, 2)},
        ]
        
        return {
            'member_stats': member_stats,
            'team_avg_rating': team_avg_rating,
            'team_feedback_count': team_feedback_count,
            'team_member_count': team_members.count(),
            'competencies': competencies,
        }

    @staticmethod
    def get_member_detailed_stats(feedbacks):
        """
        Apskaičiuoja individualaus nario detalią statistiką valdytojui pagal nario feedbakus.
        """
        from django.db.models import Avg
        
        # Aggregate stats
        avg_rating = feedbacks.aggregate(Avg('rating'))['rating__avg'] or 0
        competency_averages = feedbacks.aggregate(
            teamwork=Avg('teamwork_rating'),
            communication=Avg('communication_rating'),
            initiative=Avg('initiative_rating'),
            technical_skills=Avg('technical_skills_rating'),
            problem_solving=Avg('problem_solving_rating')
        )
        competencies = [
            {'name': _('Komandinis Darbas'), 'score': round(competency_averages.get('teamwork') or 0, 2)},
            {'name': _('Komunikacija'), 'score': round(competency_averages.get('communication') or 0, 2)},
            {'name': _('Iniciatyvumas'), 'score': round(competency_averages.get('initiative') or 0, 2)},
            {'name': _('Techninės Žinios'), 'score': round(competency_averages.get('technical_skills') or 0, 2)},
            {'name': _('Problemų Sprendimas'), 'score': round(competency_averages.get('problem_solving') or 0, 2)},
        ]
        
        # Collect all keywords
        all_keywords = []
        for fb in feedbacks:
            keywords = [kw.strip() for kw in fb.keywords.split(',') if kw.strip()]
            all_keywords.extend(keywords)
            
        return {
            'avg_rating': round(avg_rating, 2),
            'competencies': competencies,
            'keywords': list(set(all_keywords)),
        }

def extract_feedback_features_task(feedback_id):
    """
    Foninė užduotis, skirta AI išskirti stiprybes ir silpnybes iš atsiliepimo 
    naudojant Google Gemini ir išsaugoti jas atgal į Feedback modelį.
    """
    from feedbackas.models import Feedback
    from feedbackas.ai_service import OpenRouterService
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        feedback = Feedback.objects.get(id=feedback_id)
        user = feedback.feedback_request.requester
        company = user.profile.company_link if hasattr(user, 'profile') else None
        
        extracted_data = OpenRouterService.extract_strengths_weaknesses(
            feedback.feedback, 
            feedback.comments,
            user=user,
            company=company
        )
        
        # Update the feedback object with extracted data
        feedback.extracted_strengths = extracted_data.get("strengths", [])
        feedback.extracted_improvements = extracted_data.get("improvements", [])
        feedback.save(update_fields=['extracted_strengths', 'extracted_improvements'])
        
        logger.info(f"AI extraction completed successfully for feedback ID {feedback_id}")
        return True
    except Feedback.DoesNotExist:
        logger.error(f"Feedback ID {feedback_id} not found during AI extraction.")
        return False
    except Exception as e:
        logger.error(f"Failed to extract strengths and improvements in background task for feedback {feedback_id}: {e}")
        return False


# ──────────────────────────────────────────────────────────
# Email notification services (designed for Django Q async)
# ──────────────────────────────────────────────────────────

def _prepare_and_send_email(body, subject, recipient_email):
    """
    Pagalbinė funkcija: siunčia el. laišką ir plain text, ir HTML formatu.
    HTML versijoje \\n paverčiami <br>, o <a> nuorodos ir <img> paveiksliukai veikia.
    """
    from django.core.mail import send_mail
    import re

    # Plain text versija: konvertuojame HTML elementus į skaitomą tekstą
    plain_body = re.sub(r'<a\s+[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r'\2 (\1)', body, flags=re.IGNORECASE | re.DOTALL)
    plain_body = re.sub(r'<img\s+[^>]*alt=["\']([^"\']*)["\'][^>]*/?\s*>', r'[\1]', plain_body, flags=re.IGNORECASE)
    plain_body = re.sub(r'<img\s+[^>]*/?\s*>', '[Paveiksliukas]', plain_body, flags=re.IGNORECASE)
    plain_body = re.sub(r'<[^>]+>', '', plain_body)

    # HTML versija: \\n → <br>
    html_body = body.replace('\n', '<br>')

    send_mail(
        subject,
        plain_body,
        'noreply@orbigrow.lt',
        [recipient_email],
        fail_silently=False,
        html_message=html_body,
    )


def send_new_survey_email(recipient_user_id, requester_name, project_name):
    """
    Siunčia el. laišką vartotojui, kai jam priskiriama nauja apklausa (klausimynas).
    Naudojamas šablonas iš EmailTemplate modelio.
    """
    import logging
    logger = logging.getLogger(__name__)
    try:
        from django.contrib.auth.models import User
        from feedbackas.models import EmailTemplate

        recipient = User.objects.get(id=recipient_user_id)
        if not recipient.email:
            logger.warning(f"Vartotojas {recipient.username} (ID: {recipient_user_id}) neturi el. pašto adreso. Laiškas neišsiųstas.")
            return False

        email_template = EmailTemplate.load()

        recipient_name = recipient.get_full_name() or recipient.username

        # Pakeičiame placeholder'ius el. laiško tekste
        body = email_template.new_survey_body
        body = body.replace('{vardas}', recipient_name)
        body = body.replace('{siuntejas}', requester_name)
        body = body.replace('{vertintojas}', requester_name)
        body = body.replace('{apklausa}', project_name)

        subject = email_template.new_survey_subject
        subject = subject.replace('{vardas}', recipient_name)
        subject = subject.replace('{siuntejas}', requester_name)
        subject = subject.replace('{vertintojas}', requester_name)
        subject = subject.replace('{apklausa}', project_name)

        _prepare_and_send_email(body, subject, recipient.email)
        logger.info(f"Nauja apklausa – laiškas išsiųstas: {recipient.email} (apklausa: {project_name})")
        return True
    except User.DoesNotExist:
        logger.error(f"Vartotojas ID {recipient_user_id} nerastas. Laiškas neišsiųstas.")
        return False
    except Exception as e:
        logger.error(f"Klaida siunčiant 'nauja apklausa' laišką vartotojui ID {recipient_user_id}: {e}")
        return False


def send_survey_request_email(recipient_user_id, requester_name, project_name):
    """
    Siunčia el. laišką vartotojui, kai gaunamas prašymas užpildyti atsiliepimą.
    Naudojamas šablonas iš EmailTemplate modelio.
    """
    import logging
    logger = logging.getLogger(__name__)
    try:
        from django.contrib.auth.models import User
        from feedbackas.models import EmailTemplate

        recipient = User.objects.get(id=recipient_user_id)
        if not recipient.email:
            logger.warning(f"Vartotojas {recipient.username} (ID: {recipient_user_id}) neturi el. pašto adreso. Laiškas neišsiųstas.")
            return False

        email_template = EmailTemplate.load()

        recipient_name = recipient.get_full_name() or recipient.username

        # Pakeičiame placeholder'ius el. laiško tekste
        body = email_template.survey_request_body
        body = body.replace('{vardas}', recipient_name)
        body = body.replace('{siuntejas}', requester_name)
        body = body.replace('{vertintojas}', requester_name)
        body = body.replace('{apklausa}', project_name)

        subject = email_template.survey_request_subject
        subject = subject.replace('{vardas}', recipient_name)
        subject = subject.replace('{siuntejas}', requester_name)
        subject = subject.replace('{vertintojas}', requester_name)
        subject = subject.replace('{apklausa}', project_name)

        _prepare_and_send_email(body, subject, recipient.email)
        logger.info(f"Prašymas apklausai – laiškas išsiųstas: {recipient.email} (apklausa: {project_name})")
        return True
    except User.DoesNotExist:
        logger.error(f"Vartotojas ID {recipient_user_id} nerastas. Laiškas neišsiųstas.")
        return False
    except Exception as e:
        logger.error(f"Klaida siunčiant 'prašymas apklausai' laišką vartotojui ID {recipient_user_id}: {e}")
        return False


def send_feedback_received_email(recipient_user_id, evaluator_name, project_name):
    """
    Siunčia el. laišką vartotojui (prašytojui), kai jo prašytas atsiliepimas yra užpildytas.
    Naudojamas šablonas iš EmailTemplate modelio.
    """
    import logging
    logger = logging.getLogger(__name__)
    try:
        from django.contrib.auth.models import User
        from feedbackas.models import EmailTemplate

        recipient = User.objects.get(id=recipient_user_id)
        if not recipient.email:
            logger.warning(f"Vartotojas {recipient.username} (ID: {recipient_user_id}) neturi el. pašto adreso. Laiškas neišsiųstas.")
            return False

        email_template = EmailTemplate.load()

        recipient_name = recipient.get_full_name() or recipient.username

        # Pakeičiame placeholder'ius el. laiško tekste
        body = email_template.feedback_received_body
        body = body.replace('{vardas}', recipient_name)
        body = body.replace('{vertintojas}', evaluator_name)
        body = body.replace('{siuntejas}', evaluator_name)
        body = body.replace('{apklausa}', project_name)

        # Pakeičiame placeholder'ius el. laiško temoje
        subject = email_template.feedback_received_subject
        subject = subject.replace('{vardas}', recipient_name)
        subject = subject.replace('{vertintojas}', evaluator_name)
        subject = subject.replace('{siuntejas}', evaluator_name)
        subject = subject.replace('{apklausa}', project_name)

        _prepare_and_send_email(body, subject, recipient.email)
        logger.info(f"Gautas įvertinimas – laiškas išsiųstas: {recipient.email} (vertintojas: {evaluator_name})")
        return True
    except User.DoesNotExist:
        logger.error(f"Vartotojas ID {recipient_user_id} nerastas. Laiškas neišsiųstas.")
        return False
    except Exception as e:
        logger.error(f"Klaida siunčiant 'gautas įvertinimas' laišką vartotojui ID {recipient_user_id}: {e}")
        return False


class RiskAnalysisService:
    """
    Išėjimo rizikos ir perdegimo indikatoriaus (Flight & Burnout Risk Radar) analitinis servisas.
    Apdoroja nuotaikos, krūvio, tarpusavio pripažinimo ir kompetencijų duomenis, užtikrindamas darbuotojų
    privatumą per kvorumo taisykles.
    """
    MIN_QUORUM = 5  # Minimalus vertinimų skaičius skyriuje privatumui užtikrinti

    BURNOUT_KEYWORDS = [
        'viršvaland', 'perdeg', 'pervarg', 'stres', 'įtamp', 'didelis krūvis', 'krūvis',
        'terminai', 'spaudim', 'nuovarg', 'išsekim', 'perkraut', 'overtime', 'burnout',
        'stress', 'exhaustion', 'workload', 'deadlines', 'fatigue', 'overwhelmed'
    ]

    FLIGHT_KEYWORDS = [
        'demotyvac', 'nepripažin', 'konflikt', 'nesusikalb', 'izoliac', 'neteisyb',
        'nėra palaikym', 'ignorav', 'atsiriboj', 'abejing', 'demotivation',
        'lack of recognition', 'conflict', 'isolation', 'disengaged', 'unfair', 'unappreciated'
    ]

    POSITIVE_KEYWORDS = [
        'ačiū', 'puikiai', 'dėkui', 'šaunuol', 'palaikym', 'įkvėp', 'motyvac',
        'komandišk', 'rezultat', 'pasiekim', 'lyder', 'iniciatyv', 'pagalba',
        'great', 'excellent', 'thanks', 'inspiring', 'helpful', 'awesome', 'support'
    ]

    @classmethod
    def analyze_company_risk(cls, company, period_days=14, user_departments=None, requesting_user=None):
        """
        Atlieka pilną įmonės / leistinų skyrių rizikų analizę pasirinktam periodui.
        """
        from datetime import timedelta
        from django.utils import timezone
        from django.db.models import Avg, Count, Q
        from users.models import Department
        from feedbackas.models import Feedback, WellbeingCheckin
        from .risk_service import evaluate_burnout_flags_for_user, can_view_manager_survey

        now = timezone.now()
        current_start = now - timedelta(days=period_days)
        previous_start = current_start - timedelta(days=period_days)
        previous_end = current_start

        # 1. Nustatome analizuojamus skyrius
        if user_departments is not None:
            departments = list(user_departments)
        elif company:
            departments = list(Department.objects.filter(company=company).order_by('name'))
        else:
            departments = []

        dept_ids = [d.id for d in departments]

        # 2. Gauname visus periodo atsiliepimus ir tiesioginius savijautos anketų atsakymus
        feedbacks_current_qs = Feedback.objects.filter(
            feedback_request__requester__profile__company_link=company,
            feedback_request__requester__profile__department_id__in=dept_ids,
            created_at__gte=current_start,
            created_at__lte=now
        ).select_related('feedback_request', 'feedback_request__requester', 'feedback_request__requester__profile')

        feedbacks_prev_qs = Feedback.objects.filter(
            feedback_request__requester__profile__company_link=company,
            feedback_request__requester__profile__department_id__in=dept_ids,
            created_at__gte=previous_start,
            created_at__lt=previous_end
        ).select_related('feedback_request', 'feedback_request__requester')

        all_current_feedbacks = list(feedbacks_current_qs)
        all_prev_feedbacks = list(feedbacks_prev_qs)

        # Savijautos anketų atsakai
        surveys_current_qs = WellbeingCheckin.objects.filter(
            Q(company=company) | Q(user__profile__company_link=company),
            Q(department_id__in=dept_ids) | Q(user__profile__department_id__in=dept_ids),
            created_at__gte=current_start,
            created_at__lte=now
        ).exclude(visibility='private').select_related('user', 'user__profile', 'department', 'department__parent')

        surveys_prev_qs = WellbeingCheckin.objects.filter(
            Q(company=company) | Q(user__profile__company_link=company),
            Q(department_id__in=dept_ids) | Q(user__profile__department_id__in=dept_ids),
            created_at__gte=previous_start,
            created_at__lt=previous_end
        ).exclude(visibility='private').select_related('user', 'user__profile', 'department', 'department__parent')

        all_current_surveys = list(surveys_current_qs)
        all_prev_surveys = list(surveys_prev_qs)

        # Skyrių darbuotojų profiliai
        from users.models import Profile
        all_member_profiles = list(Profile.objects.filter(
            department__in=departments
        ).select_related('user', 'department'))

        all_dept_user_ids = [p.user_id for p in all_member_profiles]
        latest_surveys_map = {}
        if all_dept_user_ids:
            for s in WellbeingCheckin.objects.filter(
                user_id__in=all_dept_user_ids,
                company=company,
                visibility='manager'
            ).select_related('user', 'user__profile', 'department', 'department__parent').order_by('created_at'):
                latest_surveys_map[s.user_id] = s

        # 3. Analizuojame kiekvieną skyrių
        department_risks = []
        early_alerts = []
        total_peaks = 0

        for dept in departments:
            dept_fb = [fb for fb in all_current_feedbacks if getattr(fb.feedback_request.requester.profile, 'department_id', None) == dept.id]
            dept_prev_fb = [fb for fb in all_prev_feedbacks if getattr(fb.feedback_request.requester.profile, 'department_id', None) == dept.id]
            dept_surveys = [
                s for s in all_current_surveys 
                if s.department_id == dept.id or getattr(getattr(s.user, 'profile', None), 'department_id', None) == dept.id
            ]
            dept_prev_surveys = [
                s for s in all_prev_surveys 
                if s.department_id == dept.id or getattr(getattr(s.user, 'profile', None), 'department_id', None) == dept.id
            ]

            dept_profiles = [p for p in all_member_profiles if p.department_id == dept.id]
            employee_count = len(dept_profiles)
            survey_count = len(dept_surveys)
            feedback_count = survey_count

            dept_manager_surveys = [
                s for s in dept_surveys 
                if getattr(s, 'visibility', 'anonymous') == 'manager'
                and (not requesting_user or can_view_manager_survey(requesting_user, s))
            ]
            has_manager_surveys = len(dept_manager_surveys) > 0

            # Kvorumo taisyklė: skaičiuojama tik pagal realias savijautos anketas
            has_quorum = (survey_count >= cls.MIN_QUORUM) or has_manager_surveys

            # Darbuotojų individualių rodiklių apskaičiavimas
            dept_employees = []
            for profile in dept_profiles:
                u = profile.user
                emp_fb = [fb for fb in dept_fb if fb.feedback_request.requester_id == u.id]
                # Individualiam darbuotojui rodomos TIK vadovui skirtos anketos (1-on-1), kad nebūtų pažeistas anonimiškumas.
                # Vadovas gali matyti savo paties rodiklius, o kitų darbuotojų – tik jei turi vadovo prieigą.
                can_see_emp = (requesting_user and u.id == requesting_user.id) or (not requesting_user)
                emp_mgr_surveys = [
                    s for s in dept_surveys 
                    if s.user_id == u.id 
                    and getattr(s, 'visibility', 'anonymous') == 'manager'
                    and (can_see_emp or can_view_manager_survey(requesting_user, s))
                ]
                user_latest_survey = latest_surveys_map.get(u.id)
                if user_latest_survey and not can_see_emp and not can_view_manager_survey(requesting_user, user_latest_survey):
                    user_latest_survey = None

                active_survey = emp_mgr_surveys[0] if emp_mgr_surveys else user_latest_survey
                is_past = (not emp_mgr_surveys) and (user_latest_survey is not None)

                # Vertiname Raudonos ir Geltonos vėliavų riziką pagal anketų istoriją
                user_flags = evaluate_burnout_flags_for_user(u.id, company=company)
                is_rf = user_flags['is_red_flag']
                is_yf = user_flags['is_yellow_flag']

                if active_survey:
                    emp_m = cls._calculate_metrics(surveys=[active_survey])
                    b_score = emp_m['burnout_score']
                    f_score = emp_m['flight_score']
                    r_score = emp_m['recognition_score']
                    peaks = emp_m['workload_peaks']
                    trig = cls._determine_dominant_trigger(emp_m)
                    has_data = True
                else:
                    b_score = None
                    f_score = None
                    r_score = None
                    peaks = 0
                    trig = _('Savijautos anketa dar nepildyta')
                    has_data = False
                    is_past = False

                # Pritaiko vėliavų svorį – balai nėra tiesiog suvidurkinami
                if is_rf:
                    b_score = max(b_score or 0, 85)
                    b_level = 'critical'
                    trig = _('Raudona vėliava: išsekimas ir atsiribojimas (2+ apklausos iš eilės)')
                elif is_yf:
                    b_score = max(b_score or 0, 65)
                    b_level = 'high' if b_level in ('low', 'medium', 'unknown') else b_level
                    trig = _('Geltona vėliava: perkrova / kontrolės stoka > 2 sav.')
                else:
                    b_level = cls._determine_risk_level(b_score) if b_score is not None else 'unknown'

                f_level = cls._determine_risk_level(f_score) if f_score is not None else 'unknown'

                latest_mgr_s = active_survey

                first_l = u.first_name[:1] if u.first_name else ''
                last_l = u.last_name[:1] if u.last_name else ''
                initials = (first_l + last_l).upper() if (first_l or last_l) else (u.username[:2].upper() if u.username else '??')

                avatar_url = None
                try:
                    if profile.image and profile.image.name and profile.image.name != 'default.jpg':
                        avatar_url = profile.image.url
                except Exception:
                    avatar_url = None

                dept_employees.append({
                    'user_id': u.id,
                    'full_name': u.get_full_name() or u.username,
                    'username': u.username,
                    'email': u.email,
                    'avatar_url': avatar_url,
                    'initials': initials,
                    'feedback_count': 0,
                    'survey_count': 1 if active_survey else 0,
                    'total_responses': 1 if active_survey else 0,
                    'has_manager_survey': active_survey is not None,
                    'latest_manager_survey': latest_mgr_s,
                    'burnout_score': b_score,
                    'burnout_level': b_level,
                    'flight_score': f_score,
                    'flight_level': f_level,
                    'recognition_score': r_score,
                    'workload_peaks': peaks,
                    'dominant_trigger': trig,
                    'has_data': has_data,
                    'is_past_data': is_past,
                    'is_red_flag': is_rf,
                    'red_flag_reason': user_flags['red_flag_reason'],
                    'is_yellow_flag': is_yf,
                    'yellow_flag_reason': user_flags['yellow_flag_reason'],
                    'latest_survey_date': active_survey.created_at if active_survey else None,
                    'latest_exhaustion': getattr(active_survey, 'exhaustion_level', None) if active_survey else None,
                    'latest_engagement': getattr(active_survey, 'engagement_meaning', None) if active_survey else None,
                    'latest_workload_control': getattr(active_survey, 'workload_control', None) if active_survey else None,
                    'latest_mood': active_survey.mood_score if active_survey else None,
                    'latest_stress': active_survey.stress_level if active_survey else None,
                    'latest_energy': active_survey.energy_level if active_survey else None,
                    'latest_workload': active_survey.workload_level if active_survey else None,
                })

            def _emp_sort_key(e):
                rf = 2 if e.get('is_red_flag') else (1 if e.get('is_yellow_flag') else 0)
                sc = max(e['burnout_score'] or 0, e['flight_score'] or 0)
                mgr = 1 if e['has_manager_survey'] else 0
                return (-rf, -mgr, -sc, e['full_name'].lower())

            dept_employees.sort(key=_emp_sort_key)

            if has_quorum and dept_surveys:
                dept_metrics = cls._calculate_metrics(surveys=dept_surveys)
                prev_metrics = cls._calculate_metrics(surveys=dept_prev_surveys) if len(dept_prev_surveys) >= 2 else None

                burnout_score = dept_metrics['burnout_score']
                flight_score = dept_metrics['flight_score']
                recognition_score = dept_metrics['recognition_score']
                workload_peaks = dept_metrics['workload_peaks']
                total_peaks += workload_peaks

                # Tikriname komandos vėliavas
                dept_red_flags = sum(1 for e in dept_employees if e.get('is_red_flag'))
                dept_yellow_flags = sum(1 for e in dept_employees if e.get('is_yellow_flag'))

                if dept_red_flags > 0:
                    burnout_score = max(burnout_score or 0, 75 + min(20, dept_red_flags * 5))
                elif dept_yellow_flags > 0:
                    burnout_score = max(burnout_score or 0, 58 + min(15, dept_yellow_flags * 3))

                # Trendas lyginant su praėjusiu periodu
                if prev_metrics and prev_metrics['burnout_score'] is not None:
                    b_diff = burnout_score - prev_metrics['burnout_score']
                    f_diff = flight_score - prev_metrics['flight_score']
                else:
                    b_diff = 0
                    f_diff = 0

                burnout_trend = 'up' if b_diff > 3 else ('down' if b_diff < -3 else 'stable')
                flight_trend = 'up' if f_diff > 3 else ('down' if f_diff < -3 else 'stable')

                # Rizikos lygis
                level = cls._determine_risk_level(max(burnout_score or 0, flight_score or 0))

                # Dominuojantis trigeris
                dominant_trigger = cls._determine_dominant_trigger(dept_metrics)

                # Rekomenduojamas veiksmas
                action_plan_id = cls._determine_action_plan_id(dept_metrics)

                # Vėliavų signalai į early_alerts
                if dept_red_flags > 0:
                    early_alerts.append({
                        'id': f'rf_{dept.id}',
                        'level': 'critical',
                        'title': _('Raudona vėliava: Aukšta perdegimo rizika'),
                        'message': _('%(dept)s skyriuje nustatytas darbuotojas(-ai) (%(count)d), kuriam išsekimas ir atsiribojimas kartojasi bent 2 apklausas iš eilės.') % {
                            'dept': dept.name,
                            'count': dept_red_flags,
                        },
                        'department_name': dept.name,
                        'recommended_action': _('Nedelsiant organizuoti palaikymo 1-on-1 pokalbį ir perskirstyti kritines atsakomybes'),
                        'action_plan_id': 'action_burnout',
                    })
                elif dept_yellow_flags > 0:
                    early_alerts.append({
                        'id': f'yf_{dept.id}',
                        'level': 'warning',
                        'title': _('Geltona vėliava: Vidutinė perdegimo rizika'),
                        'message': _('%(dept)s skyriuje nustatyta, kad prasta darbo krūvio kontrolė laikosi ilgiau nei 2 savaites.') % {
                            'dept': dept.name,
                        },
                        'department_name': dept.name,
                        'recommended_action': _('Peržiūrėti užduočių prioritetus ir terminus, kol neprasidėjo lėtinis išsekimas'),
                        'action_plan_id': 'action_workload',
                    })

                # Anomalijų / perspėjimų generavimas
                if ((burnout_score or 0) >= 65 or b_diff >= 15) and dept_red_flags == 0:
                    early_alerts.append({
                        'id': f'b_{dept.id}',
                        'level': 'critical' if (burnout_score or 0) >= 75 else 'warning',
                        'title': _('Perdegimo rizikos signalas'),
                        'message': _('%(dept)s skyriuje perdegimo indeksas pasiekė %(score)d balų%(trend)s.') % {
                            'dept': dept.name,
                            'score': burnout_score,
                            'trend': f' ({"+" if b_diff > 0 else ""}{b_diff}% per periodą)' if b_diff != 0 else ''
                        },
                        'department_name': dept.name,
                        'recommended_action': _('Užduočių auditavimas ir skubus krūvio perskirstymas'),
                        'action_plan_id': 'action_burnout',
                    })

                if (flight_score or 0) >= 60 or f_diff >= 12:
                    early_alerts.append({
                        'id': f'f_{dept.id}',
                        'level': 'critical' if (flight_score or 0) >= 75 else 'warning',
                        'title': _('Išėjimo rizikos signalas'),
                        'message': _('%(dept)s skyriuje fiksuojama išėjimo rizika (%(score)d balų).') % {
                            'dept': dept.name,
                            'score': flight_score
                        },
                        'department_name': dept.name,
                        'recommended_action': _('Inicijuoti 1-on-1 pokalbį dėl motyvacijos ir pripažinimo'),
                        'action_plan_id': 'action_flight',
                    })

                if workload_peaks >= 2:
                    early_alerts.append({
                        'id': f'w_{dept.id}',
                        'level': 'warning',
                        'title': _('Viršvalandžių ir krūvio perkrovos pikas'),
                        'message': _('%(dept)s skyriuje nustatyti %(peaks)d didelio krūvio ar streso epizodai.') % {
                            'dept': dept.name,
                            'peaks': workload_peaks
                        },
                        'department_name': dept.name,
                        'recommended_action': _('Peržiūrėti projektų terminus ir prioritetus'),
                        'action_plan_id': 'action_workload',
                    })

                department_risks.append({
                    'department_id': dept.id,
                    'department_name': dept.name,
                    'employee_count': employee_count,
                    'feedback_count': survey_count,
                    'has_quorum': True,
                    'has_manager_surveys': has_manager_surveys,
                    'manager_surveys_count': len(dept_manager_surveys),
                    'burnout_score': burnout_score,
                    'burnout_level': cls._determine_risk_level(burnout_score),
                    'burnout_trend': burnout_trend,
                    'burnout_diff': f'{"+" if b_diff > 0 else ""}{b_diff}%',
                    'flight_score': flight_score,
                    'flight_level': cls._determine_risk_level(flight_score),
                    'flight_trend': flight_trend,
                    'flight_diff': f'{"+" if f_diff > 0 else ""}{f_diff}%',
                    'recognition_score': recognition_score,
                    'workload_peaks': workload_peaks,
                    'dominant_trigger': dominant_trigger,
                    'action_plan_id': action_plan_id,
                    'level': level,
                    'employees': dept_employees,
                })
            else:
                # Kvorumas nepasiektas ir nėra anketų vadovui
                department_risks.append({
                    'department_id': dept.id,
                    'department_name': dept.name,
                    'employee_count': employee_count,
                    'feedback_count': survey_count,
                    'has_quorum': False,
                    'has_manager_surveys': False,
                    'manager_surveys_count': 0,
                    'burnout_score': None,
                    'flight_score': None,
                    'recognition_score': None,
                    'workload_peaks': 0,
                    'dominant_trigger': _('Trūksta savijautos anketų duomenų (min. 4 atsakymai)'),
                    'action_plan_id': 'action_general',
                    'level': 'unknown',
                    'employees': dept_employees,
                })

        total_current_count = len(all_current_surveys)
        total_manager_surveys = len([
            s for s in all_current_surveys 
            if getattr(s, 'visibility', 'anonymous') == 'manager'
            and (not requesting_user or can_view_manager_survey(requesting_user, s))
        ])
        overall_quorum = (total_current_count >= cls.MIN_QUORUM) or (total_manager_surveys > 0)

        if overall_quorum and all_current_surveys:
            overall_metrics = cls._calculate_metrics(surveys=all_current_surveys)
            prev_overall_metrics = cls._calculate_metrics(surveys=all_prev_surveys) if len(all_prev_surveys) >= 2 else None

            overall_burnout_index = overall_metrics['burnout_score']
            overall_flight_index = overall_metrics['flight_score']
            overall_recognition_score = overall_metrics['recognition_score']

            if prev_overall_metrics and prev_overall_metrics['burnout_score'] is not None:
                ob_diff = overall_burnout_index - prev_overall_metrics['burnout_score']
                of_diff = overall_flight_index - prev_overall_metrics['flight_score']
                or_diff = overall_recognition_score - prev_overall_metrics['recognition_score']
            else:
                ob_diff = 0
                of_diff = 0
                or_diff = 0

            overall_burnout_trend = 'up' if ob_diff > 2 else ('down' if ob_diff < -2 else 'stable')
            overall_flight_trend = 'up' if of_diff > 2 else ('down' if of_diff < -2 else 'stable')
            overall_recognition_trend = 'up' if or_diff > 2 else ('down' if or_diff < -2 else 'stable')
            overall_burnout_diff = f'{"+" if ob_diff > 0 else ""}{ob_diff}%'
            overall_flight_diff = f'{"+" if of_diff > 0 else ""}{of_diff}%'
            overall_recognition_diff = f'{"+" if or_diff > 0 else ""}{or_diff}%'
        else:
            overall_burnout_index = None
            overall_flight_index = None
            overall_recognition_score = None
            overall_burnout_trend = 'stable'
            overall_flight_trend = 'stable'
            overall_recognition_trend = 'stable'
            overall_burnout_diff = '0%'
            overall_flight_diff = '0%'
            overall_recognition_diff = '0%'

        # 5. Laiko ašies duomenys Chart.js grafikui TIK iš realių savijautos anketų
        chart_data = cls._generate_chart_timeline(
            current_start,
            now,
            period_days,
            surveys=all_current_surveys
        )

        return {
            'overall_quorum': overall_quorum,
            'min_quorum': cls.MIN_QUORUM,
            'total_feedback_count': total_current_count,
            'has_manager_surveys': (total_manager_surveys > 0),
            'total_manager_surveys': total_manager_surveys,
            'overall_burnout_index': overall_burnout_index,
            'overall_burnout_level': cls._determine_risk_level(overall_burnout_index),
            'overall_burnout_trend': overall_burnout_trend,
            'overall_burnout_diff': overall_burnout_diff,
            'overall_flight_index': overall_flight_index,
            'overall_flight_level': cls._determine_risk_level(overall_flight_index),
            'overall_flight_trend': overall_flight_trend,
            'overall_flight_diff': overall_flight_diff,
            'overall_recognition_score': overall_recognition_score,
            'overall_recognition_trend': overall_recognition_trend,
            'overall_recognition_diff': overall_recognition_diff,
            'total_workload_peaks': total_peaks,
            'department_risks': department_risks,
            'early_alerts': early_alerts,
            'chart_data': chart_data,
            'period_days': period_days,
            'action_plans': cls.get_action_plans(),
        }

    @classmethod
    def _calculate_metrics(cls, surveys=None, feedbacks=None):
        """
        Apskaičiuoja perdegimo, išėjimo ir pripažinimo rodiklius TIK iš realių savijautos anketų sąrašo.
        """
        surveys = surveys or []

        if not surveys:
            return {
                'burnout_score': None,
                'flight_score': None,
                'recognition_score': None,
                'workload_peaks': 0,
                'avg_mood': None,
                'avg_energy': None,
                'avg_stress': None,
                'avg_workload': None,
                'strain_ratio': 0.0,
                'flight_ratio': 0.0,
                'survey_count': 0,
                'has_data': False,
            }

        total_surveys = len(surveys)
        avg_exhaustion = sum(getattr(s, 'exhaustion_level', 3) for s in surveys) / total_surveys
        avg_engagement = sum(getattr(s, 'engagement_meaning', 3) for s in surveys) / total_surveys
        avg_workload_ctrl = sum(getattr(s, 'workload_control', 3) for s in surveys) / total_surveys
        avg_mood = sum(getattr(s, 'mood_score', 3) for s in surveys) / total_surveys
        avg_energy = sum(getattr(s, 'energy_level', 5) for s in surveys) / total_surveys
        avg_stress = sum(getattr(s, 'stress_level', 5) for s in surveys) / total_surveys
        avg_workload = sum(getattr(s, 'workload_level', 3) for s in surveys) / total_surveys

        # 1. Perdegimo indeksas (0 - 100):
        # Didelis stresas + didelis darbo krūvis + maža energija
        stress_factor = (avg_stress / 10.0) * 40.0
        workload_factor = (avg_workload / 5.0) * 35.0
        energy_deficit = ((10.0 - avg_energy) / 10.0) * 25.0
        survey_burnout = int(round(stress_factor + workload_factor + energy_deficit))

        # 2. Išėjimo rizika (Flight Risk 0 - 100%):
        # Žema nuotaika + nuolatinis perdegimas
        mood_deficit = ((5.0 - avg_mood) / 5.0) * 45.0
        survey_flight = int(round(mood_deficit + (survey_burnout * 0.55)))

        # 3. Pripažinimo / klimato indeksas:
        survey_recog = int(round((avg_mood / 5.0) * 100.0))
        survey_peaks = sum(1 for s in surveys if getattr(s, 'workload_level', 3) >= 4 or getattr(s, 'stress_level', 5) >= 8)

        strain_ratio = 0.0
        flight_ratio = 0.0
        for s in surveys:
            if getattr(s, 'comment', None):
                t = s.comment.lower()
                if any(k in t for k in cls.BURNOUT_KEYWORDS):
                    strain_ratio = max(strain_ratio, 0.35)
                if any(k in t for k in cls.FLIGHT_KEYWORDS):
                    flight_ratio = max(flight_ratio, 0.3)

        return {
            'burnout_score': min(100, max(0, survey_burnout)),
            'flight_score': min(100, max(0, survey_flight)),
            'recognition_score': min(100, max(0, survey_recog)),
            'workload_peaks': survey_peaks,
            'avg_exhaustion': round(avg_exhaustion, 1),
            'avg_engagement': round(avg_engagement, 1),
            'avg_workload_ctrl': round(avg_workload_ctrl, 1),
            'avg_mood': round(avg_mood, 1),
            'avg_energy': round(avg_energy, 1),
            'avg_stress': round(avg_stress, 1),
            'avg_workload': round(avg_workload, 1),
            'strain_ratio': strain_ratio,
            'flight_ratio': flight_ratio,
            'survey_count': total_surveys,
            'has_data': True,
        }

    @classmethod
    def _determine_risk_level(cls, score):
        if score is None:
            return 'unknown'
        if score >= 75:
            return 'critical'
        elif score >= 55:
            return 'high'
        elif score >= 35:
            return 'medium'
        return 'low'

    @classmethod
    def _determine_dominant_trigger(cls, metrics):
        """Nustato pagrindinį veiksnį, darantį įtaką rizikos rodikliams."""
        if not metrics or not metrics.get('has_data'):
            return _('Laukiama savijautos anketų')
        if (metrics.get('avg_workload') and metrics['avg_workload'] >= 3.8) or (metrics.get('avg_stress') and metrics['avg_stress'] >= 7.0) or metrics.get('strain_ratio', 0) >= 0.25:
            return _('Intensyvus darbo krūvis ir terminų spaudimas')
        elif metrics.get('avg_energy') is not None and metrics['avg_energy'] < 5.0:
            return _('Krintanti darbuotojų energija ir įsitraukimas')
        elif (metrics.get('avg_mood') is not None and metrics['avg_mood'] < 3.0) or metrics.get('flight_ratio', 0) >= 0.2:
            return _('Demotyvacijos ir atsiribojimo signalai')
        return _('Stabilus darbo ritmas ir subalansuota aplinka')

    @classmethod
    def _determine_action_plan_id(cls, metrics):
        b_score = (metrics.get('burnout_score') or 0) if metrics else 0
        f_score = (metrics.get('flight_score') or 0) if metrics else 0
        if b_score >= f_score:
            return 'action_burnout' if b_score >= 50 else 'action_workload'
        else:
            return 'action_flight' if f_score >= 50 else 'action_recognition'

    @classmethod
    def _generate_chart_timeline(cls, start_date, end_date, period_days, surveys=None, feedbacks=None, has_quorum=True):
        """Generuoja laiko ašies taškus Chart.js grafikui TIK iš realių savijautos anketų."""
        from datetime import timedelta

        surveys = surveys or []

        if period_days <= 7:
            steps = 7
        elif period_days <= 14:
            steps = 7
        elif period_days <= 30:
            steps = 10
        else:
            steps = 12

        step_delta = (end_date - start_date) / steps
        labels = []
        burnout_series = []
        mood_series = []
        recognition_series = []

        if not surveys:
            for i in range(steps):
                window_start = start_date + (step_delta * i)
                window_end = window_start + step_delta
                labels.append(window_end.strftime('%m-%d'))
                burnout_series.append(None)
                mood_series.append(None)
                recognition_series.append(None)
            return {
                'labels': labels,
                'burnout_series': burnout_series,
                'mood_series': mood_series,
                'recognition_series': recognition_series,
                'has_data': False,
            }

        has_any_point = False
        for i in range(steps):
            window_start = start_date + (step_delta * i)
            window_end = window_start + step_delta
            labels.append(window_end.strftime('%m-%d'))

            window_surveys = [s for s in surveys if window_start <= s.created_at <= window_end]
            if window_surveys:
                m = cls._calculate_metrics(surveys=window_surveys)
                burnout_series.append(m['burnout_score'])
                avg_m = m['avg_mood'] if m['avg_mood'] is not None else 3.0
                mood_val = round(avg_m * 20, 1)
                mood_series.append(mood_val)
                recognition_series.append(m['recognition_score'])
                has_any_point = True
            else:
                burnout_series.append(None)
                mood_series.append(None)
                recognition_series.append(None)

        return {
            'labels': labels,
            'burnout_series': burnout_series,
            'mood_series': mood_series,
            'recognition_series': recognition_series,
            'has_data': has_any_point,
        }

    @classmethod
    def get_action_plans(cls):
        """Grąžina profesionalias 1-on-1 pokalbių gaires ir rekomendacijas vadovams."""
        return {
            'action_burnout': {
                'title': _('Perdegimo prevencija ir energijos atstatymas'),
                'subtitle': _('Rekomenduojami veiksmai, kai komandoje stebimas perdegimo rizikos kilimas'),
                'badge': _('Aukštas prioritetas'),
                'questions': [
                    _('Kaip vertini pastarųjų 2–3 savaičių darbo tempą ir asmeninį energijos lygį?'),
                    _('Kokie procesai, užduotys ar susitikimai labiausiai eikvoja tavo laiką ir sukelia įtampą?'),
                    _('Ar jauti, kad tavo prioritetai yra aiškūs, ar tenka dažnai persijunginėti tarp skubių užduočių?'),
                    _('Ką galėtume nedelsiant atidėti, deleguoti ar supaprastinti, kad sumažintume spaudimą?'),
                ],
                'action_steps': [
                    _('Atlikti komandos užduočių auditą ir sudaryti „Stop-doing“ (nebūtinų veiklų) sąrašą.'),
                    _('Apriboti skubius pranešimus ir susitikimus po darbo valandų, gerbiant poilsio laiką.'),
                    _('Suteikti darbuotojui galimybę lanksčiau planuoti darbo dieną ar pasiimti trumpą atokvėpį.'),
                    _('Po 14 dienų pakartoti trumpą būsenos patikrinimą (Check-in).'),
                ]
            },
            'action_flight': {
                'title': _('Išėjimo rizikos mažinimas ir motyvacijos stiprinimas'),
                'subtitle': _('Rekomenduojami veiksmai esant atsiribojimo ar pasitenkinimo kritimo signalams'),
                'badge': _('Svarbu'),
                'questions': [
                    _('Kaip matai savo augimą ir tobulėjimo kryptį mūsų komandoje per ateinančius 6–12 mėnesių?'),
                    _('Ar jauti, kad tavo indėlis ir pastangos yra tinkamai pastebimi bei vertinami?'),
                    _('Kas tave šiuo metu labiausiai džiugina ar, priešingai, labiausiai demotyvuoja kasdieniame darbe?'),
                    _('Kokių palaikymo ar pokyčių iš mano (vadovo) pusės labiausiai norėtum?'),
                ],
                'action_steps': [
                    _('Aptarti aiškų asmeninį augimo ar atsakomybių išplėtimo planą su konkrečiais terminais.'),
                    _('Padidinti reguliarų teigiamą grįžtamąjį ryšį ir viešą pasiekimų pripažinimą komandoje.'),
                    _('Išsiaiškinti, ar nėra paslėptų nesutarimų ar komunikacijos trikdžių su kolegomis.'),
                    _('Užfiksuoti sutartus veiksmus ir peržiūrėti pažangą po 3 savaičių.'),
                ]
            },
            'action_workload': {
                'title': _('Darbo krūvio subalansavimas ir viršvalandžių valdymas'),
                'subtitle': _('Rekomenduojami veiksmai esant padidėjusiam užduočių srautui ir terminų spaudimui'),
                'badge': _('Rekomendacija'),
                'questions': [
                    _('Kiek realu įgyvendinti numatytus terminus išlaikant įprastas darbo valandas?'),
                    _('Kurios užduotys turi griežčiausią verslo prioritetą, o kurias galima perstumti į kitą sprintą?'),
                    _('Ar užtenka reikalingų resursų, įrankių ir kitų komandos narių pagalbos?'),
                ],
                'action_steps': [
                    _('Perskirstyti kritines užduotis tarp komandos narių, išvengiant vieno darbuotojo perkrovos.'),
                    _('Peržiūrėti projektų terminus su suinteresuotomis šalimis ir nustatyti realistinius lūkesčius.'),
                    _('Įdiegti laiko blokavimą (focus time) giluminėms užduotims atlikti be trukdžių.'),
                ]
            },
            'action_recognition': {
                'title': _('Tarpusavio pripažinimo ir komandiškumo stiprinimas'),
                'subtitle': _('Rekomenduojami veiksmai siekiant sustiprinti teigiamo grįžtamojo ryšio kultūrą'),
                'badge': _('Kultūra'),
                'questions': [
                    _('Ar komandoje pakankamai švenčiame mažas pergales ir pastebime kolegų pagalbą?'),
                    _('Koks bendradarbiavimo būdas tau labiausiai tinka ir teikia pasitenkinimą?'),
                ],
                'action_steps': [
                    _('Komandos susirinkimų metu įtraukti trumpą „Ačiū kolegai / Kudos“ dalį.'),
                    _('Inicijuoti abipusius atsiliepimų prašymus po sėkmingai užbaigtų etapų.'),
                    _('Skatinti neformalų komandos bendravimą ir palaikymo kultūrą.'),
                ]
            },
            'action_general': {
                'title': _('Komandos mikroklimato palaikymas'),
                'subtitle': _('Standartinės gairės reguliariems 1-on-1 pokalbiams'),
                'badge': _('Profilaktika'),
                'questions': [
                    _('Kaip vertini bendrą komandos atmosferą ir tarpusavio pasitikėjimą?'),
                    _('Kokie maži pokyčiai padėtų jaustis dar geriau kasdieniame darbe?'),
                ],
                'action_steps': [
                    _('Išlaikyti reguliarių (kas 2–3 savaites) 1-on-1 pokalbių ritmą.'),
                    _('Klausytis aktyviai ir fiksuoti ankstyvus signalus iki jiems virstant problemomis.'),
                ]
            }
        }