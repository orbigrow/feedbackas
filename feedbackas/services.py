from django.utils.translation import gettext as _
from django.conf import settings
from django.db.models import Avg
from .models import Feedback, FeedbackRequest
from django.contrib.auth.models import User

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

def generate_ai_feedback_task(ratings, keywords, comments, existing_feedback, colleague_name, user_id=None, language='lt'):
    from .ai_service import OpenRouterService
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
        language=language
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
            avg_rating=Avg('received_requests__feedback__rating', filter=Q(received_requests__status='completed')),
            feedback_count=Count('received_requests__feedback', filter=Q(received_requests__status='completed'))
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
    from .models import Feedback
    from .ai_service import OpenRouterService
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
        from .models import EmailTemplate

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
        from .models import EmailTemplate

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
        from .models import EmailTemplate

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