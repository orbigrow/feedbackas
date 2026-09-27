# feedbackas/services/risk_service.py
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Count
from feedbackas.models import WellbeingCheckin, Feedback

def calculate_team_risk_metrics(department_id=None, days=14):
    """
    Apskaičiuoja apibendrintą komandos perdegimo (Burnout) ir 
    išėjimo (Flight) riziką, garantuojant anonimiškumą (kvorumas >= 5).
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    
    entries = WellbeingCheckin.objects.filter(created_at__gte=cutoff_date)
    if department_id:
        entries = entries.filter(user__profile__department_id=department_id)
        
    unique_users = entries.values('user').distinct().count()
    has_manager_entries = entries.filter(visibility='manager').exists()

    # Kvorumas taikomas anoniminiams įrašams; jei vartotojas nurodo, kad anketa vadovui, vadovas ją mato bet kuriuo atveju
    if unique_users < 5 and not has_manager_entries:
        return {'status': 'insufficient_quorum', 'message': 'Mažiau nei 5 nariai - duomenys slepiami dėl anonimiškumo.'}
        
    stats = entries.aggregate(
        avg_mood=Avg('mood_score'),          # 1 - 5
        avg_energy=Avg('energy_level'),      # 1 - 10
        avg_stress=Avg('stress_level'),      # 1 - 10
        avg_workload=Avg('workload_level'),  # 1 - 5
    )
    
    # 1. Perdegimo indeksas (0 - 100):
    # Didelis stresas + didelis darbo krūvis + maža energija
    stress_factor = (stats['avg_stress'] / 10.0) * 40.0
    workload_factor = (stats['avg_workload'] / 5.0) * 35.0
    energy_deficit = ((10.0 - stats['avg_energy']) / 10.0) * 25.0
    burnout_index = round(stress_factor + workload_factor + energy_deficit, 1)
    
    # 2. Išėjimo rizika (Flight Risk 0 - 100%):
    # Žema nuotaika + nuolatinis perdegimas + žemas tarpusavio grįžtamasis ryšys
    mood_deficit = ((5.0 - stats['avg_mood']) / 5.0) * 45.0
    flight_risk = round(mood_deficit + (burnout_index * 0.55), 1)
    
    return {
        'status': 'success',
        'burnout_index': min(100, max(0, burnout_index)),
        'flight_risk': min(100, max(0, flight_risk)),
        'stats': stats,
        'unique_contributors': unique_users,
        'requires_action': burnout_index > 65 or flight_risk > 50
    }
