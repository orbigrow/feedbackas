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


class HeroSlideTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(username='superadmin', password='password', email='admin@test.com')
        self.regular_user = User.objects.create_user(username='regular', password='password', email='user@test.com')

    def test_save_and_delete_hero_slide_as_superuser(self):
        self.client.force_login(self.superuser)
        # Create slide
        response = self.client.post('/superadmin/hero-slides/save/', {
            'title': 'Test title',
            'title_en': 'Test title EN',
            'description': 'Test desc',
            'description_en': 'Test desc EN',
            'button_text': 'Click here',
            'button_text_en': 'Click EN',
            'button_url': '/test-url/',
            'order': 1,
            'is_active': 'on'
        })
        self.assertEqual(response.status_code, 302)
        from .models import HeroSlide
        slide = HeroSlide.objects.get(title='Test title')
        self.assertEqual(slide.title_en, 'Test title EN')
        self.assertEqual(slide.button_text, 'Click here')
        self.assertEqual(slide.button_url, '/test-url/')
        self.assertTrue(slide.is_active)

        # Update slide
        response = self.client.post('/superadmin/hero-slides/save/', {
            'slide_id': slide.id,
            'title': 'Updated title',
            'title_en': 'Updated EN',
            'description': 'Updated desc',
            'description_en': 'Updated desc EN',
            'button_text': 'Updated btn',
            'button_text_en': 'Updated btn EN',
            'button_url': '/updated-url/',
            'order': 2,
            'is_active': 'on'
        })
        self.assertEqual(response.status_code, 302)
        slide.refresh_from_db()
        self.assertEqual(slide.title, 'Updated title')
        self.assertEqual(slide.order, 2)

        # Delete slide
        response = self.client.post(f'/superadmin/hero-slides/{slide.id}/delete/')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(HeroSlide.objects.filter(id=slide.id).exists())

    def test_regular_user_cannot_access_hero_slides(self):
        self.client.force_login(self.regular_user)
        response = self.client.post('/superadmin/hero-slides/save/', {'title': 'Hack'})
        self.assertEqual(response.status_code, 302)
        from .models import HeroSlide
        self.assertFalse(HeroSlide.objects.filter(title='Hack').exists())

    def test_save_carousel_interval(self):
        self.client.force_login(self.superuser)
        response = self.client.post('/superadmin/hero-slides/interval/', {
            'home_carousel_interval': '9'
        })
        self.assertEqual(response.status_code, 302)
        from .models import PageDescription
        p = PageDescription.load()
        self.assertEqual(p.home_carousel_interval, 9)


class CustomPageTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(username='admin2', password='password', email='admin2@test.com')
        self.regular_user = User.objects.create_user(username='regular2', password='password', email='regular2@test.com')

    def test_save_custom_page_and_view(self):
        self.client.force_login(self.superuser)
        response = self.client.post('/superadmin/custom-pages/save/', {
            'title': 'Grįžtamojo ryšio gairės',
            'slug': 'griztamojo-rysio-gaires',
            'content': '<h2>Mūsų taisyklės</h2><p>Turinys čia...</p>',
            'is_published': 'true'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['url'], '/p/griztamojo-rysio-gaires/')

        # View the created page
        page_response = self.client.get('/p/griztamojo-rysio-gaires/')
        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, 'Grįžtamojo ryšio gairės')
        self.assertContains(page_response, 'Mūsų taisyklės')

    def test_upload_page_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.superuser)
        test_file = SimpleUploadedFile("test.png", b"fake_image_content", content_type="image/png")
        response = self.client.post('/superadmin/custom-pages/upload-image/', {'file': test_file})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('location', data)
        self.assertTrue(data['location'].startswith('/media/custom_pages/'))


class DescriptionsSubpagesTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(username='subadmin', password='password', email='subadmin@test.com')
        self.client.force_login(self.superuser)

    def test_descriptions_redirects_to_hero(self):
        response = self.client.get('/superadmin/descriptions/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/superadmin/descriptions/hero/')

    def test_descriptions_hero_page(self):
        response = self.client.get('/superadmin/descriptions/hero/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hero Karuselė ir Pagrindinis Puslapis')

    def test_descriptions_index_page_and_save(self):
        response = self.client.get('/superadmin/descriptions/index/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pradžios Puslapis (Index)')

        post_resp = self.client.post('/superadmin/descriptions/index/', {
            'index_hero_title': 'Nauja pradžios antraštė',
            'index_hero_title_en': 'New index title',
            'index_hero_desc': 'Naujas aprašymas',
            'index_hero_desc_en': 'New description',
            'index_features_title': 'Funkcijos',
            'index_features_title_en': 'Features',
            'index_feature1_title': 'F1',
            'index_feature1_title_en': 'F1 EN',
            'index_feature1_desc': 'F1 D',
            'index_feature1_desc_en': 'F1 D EN',
            'index_feature2_title': 'F2',
            'index_feature2_title_en': 'F2 EN',
            'index_feature2_desc': 'F2 D',
            'index_feature2_desc_en': 'F2 D EN',
            'index_feature3_title': 'F3',
            'index_feature3_title_en': 'F3 EN',
            'index_feature3_desc': 'F3 D',
            'index_feature3_desc_en': 'F3 D EN',
            'index_howitworks_title': 'Kaip veikia',
            'index_howitworks_title_en': 'How it works',
            'index_step1_title': 'S1',
            'index_step1_title_en': 'S1 EN',
            'index_step1_desc': 'S1 D',
            'index_step1_desc_en': 'S1 D EN',
            'index_step2_title': 'S2',
            'index_step2_title_en': 'S2 EN',
            'index_step2_desc': 'S2 D',
            'index_step2_desc_en': 'S2 D EN',
            'index_step3_title': 'S3',
            'index_step3_title_en': 'S3 EN',
            'index_step3_desc': 'S3 D',
            'index_step3_desc_en': 'S3 D EN',
            'index_cta_title': 'CTA',
            'index_cta_title_en': 'CTA EN',
            'index_cta_desc': 'CTA D',
            'index_cta_desc_en': 'CTA D EN',
        })
        self.assertEqual(post_resp.status_code, 302)
        from .models import PageDescription
        p = PageDescription.load()
        self.assertEqual(p.index_hero_title, 'Nauja pradžios antraštė')

    def test_descriptions_about_page_and_save(self):
        response = self.client.get('/superadmin/descriptions/about/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Puslapis „Apie mus“')

        post_resp = self.client.post('/superadmin/descriptions/about/', {
            'about_hero_title': 'Apie mus nauja antraštė',
            'about_hero_title_en': 'About us new title',
            'about_hero_desc': 'Apie mus naujas aprašymas',
            'about_hero_desc_en': 'About us new desc',
            'about_mission_title': 'Misija',
            'about_mission_title_en': 'Mission',
            'about_mission_desc1': 'M1',
            'about_mission_desc1_en': 'M1 EN',
            'about_mission_desc2': 'M2',
            'about_mission_desc2_en': 'M2 EN',
            'about_values_title': 'Vertybės',
            'about_values_title_en': 'Values',
            'about_values_subtitle': 'Sub',
            'about_values_subtitle_en': 'Sub EN',
            'about_value1_title': 'V1',
            'about_value1_title_en': 'V1 EN',
            'about_value1_desc': 'V1 D',
            'about_value1_desc_en': 'V1 D EN',
            'about_value2_title': 'V2',
            'about_value2_title_en': 'V2 EN',
            'about_value2_desc': 'V2 D',
            'about_value2_desc_en': 'V2 D EN',
            'about_value3_title': 'V3',
            'about_value3_title_en': 'V3 EN',
            'about_value3_desc': 'V3 D',
            'about_value3_desc_en': 'V3 D EN',
            'about_value4_title': 'V4',
            'about_value4_title_en': 'V4 EN',
            'about_value4_desc': 'V4 D',
            'about_value4_desc_en': 'V4 D EN',
        })
        self.assertEqual(post_resp.status_code, 302)
        from .models import PageDescription
        p = PageDescription.load()
        self.assertEqual(p.about_hero_title, 'Apie mus nauja antraštė')

    def test_descriptions_security_page_and_save(self):
        response = self.client.get('/superadmin/descriptions/security/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Saugumo Užtikrinimas')

        post_resp = self.client.post('/superadmin/descriptions/security/', {
            'security_content': '<p>Atnaujintas saugumo tekstas</p>',
            'security_content_en': '<p>Updated security content</p>',
        })
        self.assertEqual(post_resp.status_code, 302)
        from .models import PageDescription
        p = PageDescription.load()
        self.assertEqual(p.security_content, '<p>Atnaujintas saugumo tekstas</p>')

    def test_descriptions_pages_and_delete(self):
        from .models import CustomPage
        page = CustomPage.objects.create(
            title='Trinamas puslapis',
            slug='trinamas-puslapis',
            content='<p>Test</p>',
            is_published=True
        )
        response = self.client.get('/superadmin/descriptions/pages/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Trinamas puslapis')

        del_resp = self.client.post(f'/superadmin/custom-pages/{page.id}/delete/')
        self.assertEqual(del_resp.status_code, 302)
        self.assertFalse(CustomPage.objects.filter(id=page.id).exists())


class OnboardingTourTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='TourCorp', is_active=True)
        self.user = User.objects.create_user(username='touruser', password='password123')
        self.profile = self.user.profile
        self.profile.company_link = self.company
        self.profile.save()

    def test_complete_onboarding_tour_unauthenticated(self):
        response = self.client.post('/api/complete-tour/')
        self.assertEqual(response.status_code, 302)

    def test_complete_onboarding_tour_success(self):
        self.client.force_login(self.user)
        self.assertFalse(self.profile.has_completed_tour)

        response = self.client.post('/api/complete-tour/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'ok')
        self.assertTrue(data.get('has_completed_tour'))

        self.profile.refresh_from_db()
        self.assertTrue(self.profile.has_completed_tour)

    def test_reset_onboarding_tour(self):
        self.profile.has_completed_tour = True
        self.profile.save()
        self.client.force_login(self.user)

        response = self.client.post('/api/complete-tour/', {'reset': 'true'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'ok')
        self.assertFalse(data.get('has_completed_tour'))

        self.profile.refresh_from_db()
        self.assertFalse(self.profile.has_completed_tour)

    def test_home_page_contains_tour_elements(self):
        self.client.force_login(self.user)
        response = self.client.get('/home/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'onboarding-tour-root')
        self.assertContains(response, 'tour-spotlight-mask')
        self.assertContains(response, 'tour-btn-request')
        self.assertContains(response, 'tour-btn-send')
        self.assertContains(response, 'tour-nav-tasks')
        self.assertContains(response, 'Kartoti turą')


class SuperadminTourDescriptionsTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(username='superadmin_tour', password='password123', email='admin_tour@test.com')
        self.regular_user = User.objects.create_user(username='regular_tour', password='password123')

    def test_tour_descriptions_get_as_superuser(self):
        self.client.force_login(self.superuser)
        response = self.client.get('/superadmin/descriptions/tour/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Svetainės turas (Onboarding)')
        self.assertContains(response, 'tour_welcome_title')

    def test_tour_descriptions_get_as_regular_user_forbidden(self):
        self.client.force_login(self.regular_user)
        response = self.client.get('/superadmin/descriptions/tour/')
        self.assertEqual(response.status_code, 302)

    def test_tour_descriptions_post_update(self):
        self.client.force_login(self.superuser)
        post_data = {
            'tour_welcome_title': 'Atnaujintas pasveikinimas',
            'tour_welcome_title_en': 'Updated welcome',
            'tour_welcome_desc': 'Naujas aprašymas',
            'tour_welcome_desc_en': 'New description',
            'tour_welcome_btn': 'Pradėkime',
            'tour_welcome_btn_en': 'Let us start',
            'tour_request_title': 'Prašykite atsiliepimo',
            'tour_request_title_en': 'Ask for feedback',
            'tour_request_desc': 'Prašymo paaiškinimas',
            'tour_request_desc_en': 'Request explanation',
            'tour_send_title': 'Siųskite atsiliepimą',
            'tour_send_title_en': 'Send review',
            'tour_send_desc': 'Siuntimo paaiškinimas',
            'tour_send_desc_en': 'Send explanation',
            'tour_tasks_title': 'Užduotys',
            'tour_tasks_title_en': 'Tasks',
            'tour_tasks_desc': 'Užduočių paaiškinimas',
            'tour_tasks_desc_en': 'Tasks explanation',
            'tour_results_title': 'Rezultatai',
            'tour_results_title_en': 'Results',
            'tour_results_desc': 'Rezultatų paaiškinimas',
            'tour_results_desc_en': 'Results explanation',
            'tour_team_title': 'Komanda',
            'tour_team_title_en': 'Team',
            'tour_team_desc': 'Komandos paaiškinimas',
            'tour_team_desc_en': 'Team explanation',
            'tour_finish_title': 'Pabaiga!',
            'tour_finish_title_en': 'Finish!',
            'tour_finish_desc': 'Viskas atlikta',
            'tour_finish_desc_en': 'All done',
            'tour_finish_btn': 'Pirmyn',
            'tour_finish_btn_en': 'Forward',
        }
        response = self.client.post('/superadmin/descriptions/tour/', post_data)
        self.assertEqual(response.status_code, 302)
        from .models import PageDescription
        p = PageDescription.load()
        self.assertEqual(p.tour_welcome_title, 'Atnaujintas pasveikinimas')
        self.assertEqual(p.tour_welcome_title_en, 'Updated welcome')


