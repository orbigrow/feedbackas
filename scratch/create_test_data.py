import os
import django
import random
from datetime import timedelta
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'feedbackas.settings')
django.setup()

from django.contrib.auth.models import User
from users.models import Company, Department, Profile
from feedbackas.models import Questionnaire, FeedbackRequest, Feedback, Trait

def generate_test_company():
    print("Kuriama testinė įmonė...")
    company, _ = Company.objects.get_or_create(
        name="UAB Demo Technologijos",
        defaults={
            "is_active": True,
            "email_domain": "orbigrow.lt",
        }
    )

    # Sukurti padalinius
    it_dept, _ = Department.objects.get_or_create(company=company, name="IT skyrius")
    sales_dept, _ = Department.objects.get_or_create(company=company, name="Pardavimų skyrius")

    # Sukurti pagrindinį testinį vartotoją (vadovą)
    demo_user, created = User.objects.get_or_create(
        username="demo",
        defaults={
            "email": "demo@orbigrow.lt",
            "first_name": "Jonas",
            "last_name": "Demo",
        }
    )
    demo_user.set_password("password123")
    demo_user.save()

    demo_profile = demo_user.profile
    demo_profile.company_link = company
    demo_profile.department = it_dept
    demo_profile.is_company_admin = True
    demo_profile.save()
    it_dept.manager = demo_user
    it_dept.save()

    # Sukurti komandos narius
    colleagues_data = [
        ("Mantas", "Kazlauskas", "mantas@orbigrow.lt", it_dept),
        ("Laura", "Petraitiene", "laura@orbigrow.lt", it_dept),
        ("Tomas", "Jonaitis", "tomas@orbigrow.lt", it_dept),
        ("Giedre", "Vasiliauskaite", "giedre@orbigrow.lt", sales_dept),
    ]

    team_users = [demo_user]
    for fn, ln, em, dept in colleagues_data:
        u, _ = User.objects.get_or_create(
            username=em.split('@')[0],
            defaults={"email": em, "first_name": fn, "last_name": ln}
        )
        u.set_password("password123")
        u.save()
        u.profile.company_link = company
        u.profile.department = dept
        u.profile.save()
        team_users.append(u)

    # Bruožai / Traits
    trait_names = ['Komunikabilumas', 'Iniciatyvumas', 'Atsakomybe', 'Kokybe', 'Komandinis darbas']
    traits = []
    for tn in trait_names:
        tr, _ = Trait.objects.get_or_create(name=tn)
        traits.append(tr)

    # Klausimynas
    q, _ = Questionnaire.objects.get_or_create(
        title="360 Bendras Vertinimas",
        created_by=demo_user
    )
    q.traits.set(traits)

    # Užduotys (FeedbackRequest) Jonui (demo_user)
    # 1. Laukiančios užduotys (Tasks to do)
    for other in team_users[1:3]:
        req, _ = FeedbackRequest.objects.get_or_create(
            requester=other,
            requested_to=demo_user,
            project_name="Sprinto apžvalga",
            defaults={
                "status": "pending",
                "due_date": timezone.now().date() + timedelta(days=7),
                "comment": "Būčiau dėkingas už grįžtamąjį ryšį apie bendradarbiavimą."
            }
        )

    # 2. Užbaigti įvertinimai (Feedback received) Jonui (demo_user)
    for other in team_users[1:4]:
        req, _ = FeedbackRequest.objects.get_or_create(
            requester=demo_user,
            requested_to=other,
            project_name="Metinis veiklos vertinimas",
            defaults={
                "status": "completed",
                "due_date": timezone.now().date() - timedelta(days=10),
            }
        )
        if not Feedback.objects.filter(feedback_request=req).exists():
            fb = Feedback.objects.create(
                feedback_request=req,
                rating=random.randint(3, 4),
                teamwork_rating=random.randint(3, 4),
                communication_rating=random.randint(3, 4),
                initiative_rating=random.randint(3, 4),
                technical_skills_rating=random.randint(3, 4),
                problem_solving_rating=random.randint(3, 4),
                keywords="atsakingas, greitas, iniciatyvus",
                comments="Puikus komandos narys!",
                feedback="Kolega rodo puikius rezultatus ir visada padeda komandai.",
                created_at=timezone.now() - timedelta(days=random.randint(2, 20))
            )

    print("Testinė įmonė ir duomenys sėkmingai sukurti!")
    print("Prisijungimo duomenys:")
    print("El. paštas / Vartotojo vardas: demo@orbigrow.lt arba demo")
    print("Slaptažodis: password123")

if __name__ == "__main__":
    generate_test_company()
