from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from users.models import Profile, Company
from .views import team_members_list
from .ai_service import parse_name_gender_vocative
from django.contrib.auth.models import AnonymousUser

class TeamMembersListTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user1 = User.objects.create_user(username='user1', password='password', first_name='User', last_name='One')
        self.company1 = Company.objects.create(name='TestCorp')
        self.user1.profile.company_link = self.company1
        self.user1.profile.save()
        
        self.user2 = User.objects.create_user(username='user2', password='password', first_name='User', last_name='Two')
        self.user2.profile.company_link = self.company1
        self.user2.profile.save()
        
        self.user3 = User.objects.create_user(username='user3', password='password', first_name='User', last_name='Three')
        self.company2 = Company.objects.create(name='AnotherCorp')
        self.user3.profile.company_link = self.company2
        self.user3.profile.save()

        self.user4 = User.objects.create_user(username='user4', password='password', first_name='User', last_name='Four')
        # User 4 has no company assigned

    def test_team_members_list_with_company(self):
        self.client.force_login(self.user1)
        response = self.client.get('/team/')
        self.assertEqual(response.status_code, 200)
        team_members = list(response.context['team_members'])
        self.assertIn(self.user2, team_members)
        self.assertNotIn(self.user1, team_members)
        self.assertNotIn(self.user3, team_members)

    def test_team_members_list_without_company(self):
        # Vartotojai be įmonės nukreipiami į '/no-company/'
        user_no_company = User.objects.create_user(username='user5', password='password')
        user_no_company.profile.company_link = None
        user_no_company.profile.save()
        
        self.client.force_login(user_no_company)
        response = self.client.get('/team/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/no-company/')

    def test_team_members_list_no_profile(self):
        # Vartotojai be profilio nukreipiami į '/no-company/'
        Profile.objects.filter(user=self.user4).delete()
        self.client.force_login(self.user4)
        response = self.client.get('/team/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/no-company/')

    def test_team_members_list_unauthenticated(self):
        request = self.factory.get('/team/')
        request.user = AnonymousUser()
        response = self.client.get('/team/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login/'))


class AILinguisticsTest(TestCase):
    def test_parse_name_gender_vocative(self):
        test_cases = [
            ('Justinas Zamarys', 'Justinas', 'Justinai', 'male'),
            ('Elena Žukauskaitė', 'Elena', 'Elena', 'female'),
            ('Rasa Petrauskienė', 'Rasa', 'Rasa', 'female'),
            ('Tomas Jonaitis', 'Tomas', 'Tomai', 'male'),
            ('Paulius Jankauskas', 'Paulius', 'Pauliau', 'male'),
            ('Eglė Šimonytė', 'Eglė', 'Egle', 'female'),
            ('Dovilė Kazlauskė', 'Dovilė', 'Dovile', 'female'),
            ('Marius Beržinis', 'Marius', 'Mariau', 'male'),
            ('Jurgis', 'Jurgis', 'Jurgi', 'male'),
            ('Kazys', 'Kazys', 'Kazy', 'male'),
            ('Sandra', 'Sandra', 'Sandra', 'female'),
            ('elena.zukauskas62146@powerup.lt', 'Elena', 'Elena', 'female'),
        ]
        for full_name, exp_first, exp_voc, exp_gender in test_cases:
            with self.subTest(full_name=full_name):
                fn, ln, voc, g = parse_name_gender_vocative(full_name)
                self.assertEqual(fn, exp_first)
                self.assertEqual(voc, exp_voc)
                self.assertEqual(g, exp_gender)

