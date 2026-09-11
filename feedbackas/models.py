from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class FeedbackRequest(models.Model):
    requester = models.ForeignKey(User, related_name='made_requests', on_delete=models.CASCADE)
    requested_to = models.ForeignKey(User, related_name='received_requests', on_delete=models.CASCADE)
    project_name = models.CharField(max_length=255)
    questionnaire = models.ForeignKey('Questionnaire', on_delete=models.SET_NULL, null=True, blank=True, related_name='feedback_requests')
    comment = models.TextField(blank=True, null=True)
    due_date = models.DateField()
    status = models.CharField(max_length=20, default='pending')
    is_self_initiated = models.BooleanField(default=False, help_text='True jei atsiliepimas inicijuotas paties vertintojo, o ne paprašytas')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Feedback request from {self.requester} to {self.requested_to} for {self.project_name}"

class Feedback(models.Model):
    feedback_request = models.OneToOneField(FeedbackRequest, on_delete=models.CASCADE)
    rating = models.IntegerField(help_text="Bendras įvertinimas")
    # Pridėkite trūkstamus laukus:
    teamwork_rating = models.IntegerField(default=5)
    communication_rating = models.IntegerField(default=5)
    initiative_rating = models.IntegerField(default=5)
    technical_skills_rating = models.IntegerField(default=5)
    problem_solving_rating = models.IntegerField(default=5)

    keywords = models.CharField(max_length=255)
    comments = models.TextField(blank=True)
    feedback = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    # AI išskirtos savybės iš atsiliepimo ir komentaro
    extracted_strengths = models.JSONField(default=list, blank=True)
    extracted_improvements = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Feedback for {self.feedback_request}"

class Trait(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_traits')

    def __str__(self):
        return self.name

class Questionnaire(models.Model):
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='questionnaires')
    traits = models.ManyToManyField(Trait, blank=True, related_name='questionnaires')
    is_team = models.BooleanField(default=False)
    target_department = models.ForeignKey('users.Department', null=True, blank=True, on_delete=models.SET_NULL, related_name='team_questionnaires')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title

class TraitRating(models.Model):
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE, related_name='trait_ratings')
    trait = models.ForeignKey(Trait, on_delete=models.CASCADE)
    rating = models.IntegerField(default=0)

    class Meta:
        unique_together = ('feedback', 'trait')

    def __str__(self):
        return f"{self.trait.name}: {self.rating} (Feedback #{self.feedback.id})"

class AIUsageLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_usage_logs')
    company = models.ForeignKey('users.Company', on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_usage_logs')
    request_type = models.CharField(max_length=100, help_text="Pvž., 'feedback_generation', 'feedback_analysis'")
    model_name = models.CharField(max_length=100)
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    total_cost = models.DecimalField(max_digits=15, decimal_places=10, default=0.0)
    raw_response = models.JSONField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.request_type} by {self.user} ({self.total_cost}$)"

class GlobalSettings(models.Model):
    personal_form_enabled = models.BooleanField(default=True, help_text="Įjungti 'Individuali forma' funkcionalumą visai platformai.")
    team_form_enabled = models.BooleanField(default=True, help_text="Įjungti 'Komandinė forma' funkcionalumą visai platformai.")
    language_switcher_enabled = models.BooleanField(default=True, help_text="Įjungti kalbų pasirinkimą (LT/EN) visoje platformoje.")

    class Meta:
        verbose_name_plural = "Global Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(GlobalSettings, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

class PageDescription(models.Model):
    # Priežiūros režimas
    maintenance_mode = models.BooleanField(default=False, help_text="Įjungus šį režimą, pradiniame puslapyje bus rodomas 'Greitai pradėsime' pranešimas.")
    maintenance_title = models.CharField(max_length=255, default="Greitai pradėsime")
    maintenance_title_en = models.CharField(max_length=255, default="Coming Soon", blank=True)
    maintenance_desc = models.TextField(default="Šiuo metu atnaujiname sistemą. Užsukite netrukus!")
    maintenance_desc_en = models.TextField(default="We are currently updating our system. Please check back soon!", blank=True)

    # home.html (prisijungusio vartotojo pagrindinis puslapis)
    home_hero_title = models.CharField(max_length=255, default="Jūs jau žinote. Mes tiesiog randame žodžius.")
    home_hero_title_en = models.CharField(max_length=255, default="You already know. We just find the words.", blank=True)
    home_hero_desc = models.TextField(default="Pasirinkite raktinius žodžius, pridėkite komentarą — sistema per kelias sekundes pavers tai aiškiu, į augimą orientuotu grįžtamuoju ryšiu.")
    home_hero_desc_en = models.TextField(default="Select keywords, add a comment — the system will turn it into clear, growth-oriented feedback in seconds.", blank=True)

    # index.html
    index_hero_title = models.CharField(max_length=255, default="Skatinkite atvirą komandos kultūrą")
    index_hero_title_en = models.CharField(max_length=255, default="Foster an open team culture", blank=True)
    index_hero_desc = models.TextField(default="Mūsų platforma padeda lengvai rinkti ir analizuoti atsiliepimus. Išryškinkite stiprybes ir padėkite savo darbuotojams augti kartu.")
    index_hero_desc_en = models.TextField(default="Our platform helps you easily collect and analyze feedback. Highlight strengths and help your employees grow together.", blank=True)
    index_features_title = models.CharField(max_length=255, default="Kodėl verta rinktis mus?")
    index_features_title_en = models.CharField(max_length=255, default="Why choose us?", blank=True)
    index_feature1_title = models.CharField(max_length=255, default="Atviras Grįžtamasis Ryšys")
    index_feature1_title_en = models.CharField(max_length=255, default="Open Feedback", blank=True)
    index_feature1_desc = models.TextField(default="Skatinkite skaidrumą ir asmeninį augimą su atvirais, vardiniais kolegų atsiliepimais bei vertinimais.")
    index_feature1_desc_en = models.TextField(default="Encourage transparency and personal growth with open, named peer reviews and ratings.", blank=True)
    index_feature2_title = models.CharField(max_length=255, default="Dirbtinio Intelekto Įžvalgos")
    index_feature2_title_en = models.CharField(max_length=255, default="Artificial Intelligence Insights", blank=True)
    index_feature2_desc = models.TextField(default="AI algoritmai sistemina gautus atsiliepimus, išryškindami asmenines stiprybes ir aiškias sritis, kuriose vertėtų tobulėti.")
    index_feature2_desc_en = models.TextField(default="AI algorithms systematize the received feedback, highlighting personal strengths and clear areas for improvement.", blank=True)
    index_feature3_title = models.CharField(max_length=255, default="Paprasta Naudoti")
    index_feature3_title_en = models.CharField(max_length=255, default="Easy to Use", blank=True)
    index_feature3_desc = models.TextField(default="Intuityvi sąsaja tiek administratoriams, tiek darbuotojams. Pradėkite per kelias minutes.")
    index_feature3_desc_en = models.TextField(default="Intuitive interface for both administrators and employees. Get started in minutes.", blank=True)
    index_howitworks_title = models.CharField(max_length=255, default="Kaip tai veikia?")
    index_howitworks_title_en = models.CharField(max_length=255, default="How it works?", blank=True)
    index_step1_title = models.CharField(max_length=255, default="Paprašykite Atsiliepimo")
    index_step1_title_en = models.CharField(max_length=255, default="Request Feedback", blank=True)
    index_step1_desc = models.TextField(default="Pasirinkite kolegą ir išsiųskite prašymą įvertinti jūsų darbą keliais paspaudimais.")
    index_step1_desc_en = models.TextField(default="Select a colleague and send a request to evaluate your work in a few clicks.", blank=True)
    index_step2_title = models.CharField(max_length=255, default="Gaukite Įvertinimą")
    index_step2_title_en = models.CharField(max_length=255, default="Get Evaluated", blank=True)
    index_step2_desc = models.TextField(default="Kolegos atvirai atsako į išsamius kompetencijų ir asmeninių savybių klausimus.")
    index_step2_desc_en = models.TextField(default="Colleagues openly answer detailed questions about competencies and personal traits.", blank=True)
    index_step3_title = models.CharField(max_length=255, default="Analizuokite su AI")
    index_step3_title_en = models.CharField(max_length=255, default="Analyze with AI", blank=True)
    index_step3_desc = models.TextField(default="Dirbtinis intelektas praskenuoja komentarus ir pateikia aiškias stiprybes bei tobulėjimo sritis.")
    index_step3_desc_en = models.TextField(default="Artificial intelligence scans comments and provides clear strengths and areas for improvement.", blank=True)
    index_cta_title = models.CharField(max_length=255, default="Pasiruošę pagerinti komandos ryšį?")
    index_cta_title_en = models.CharField(max_length=255, default="Ready to improve team connection?", blank=True)
    index_cta_desc = models.TextField(default="Prisijunkite prie įmonių, kurios naudoja atsiliepimus savo augimui skatinti. Pradėkite nemokamą bandomąjį laikotarpį šiandien.")
    index_cta_desc_en = models.TextField(default="Join companies that use feedback to drive their growth. Start your free trial today.", blank=True)

    # apie_mus.html
    about_hero_title = models.CharField(max_length=255, default="Apie Mūsų Komandą")
    about_hero_title_en = models.CharField(max_length=255, default="About Our Team", blank=True)
    about_hero_desc = models.TextField(default="Orbigrow.lt tikslas – padėti organizacijoms sukurti atvirą grįžtamojo ryšio kultūrą ir paskatinti kiekvieno darbuotojo augimą.")
    about_hero_desc_en = models.TextField(default="Orbigrow.lt's goal is to help organizations create an open feedback culture and foster the growth of every employee.", blank=True)
    about_mission_title = models.CharField(max_length=255, default="Mūsų Misija")
    about_mission_title_en = models.CharField(max_length=255, default="Our Mission", blank=True)
    about_mission_desc1 = models.TextField(default="Tikime, kad nuolatinis ir atviras kolegų vertinimas yra pagrindinis komandos tobulėjimo variklis. Dažnai grįžtamasis ryšys įmonėse būna pamirštamas, paliekamas tik metiniams pokalbiams arba anoniminis, kas trukdo konstruktyviam dialogui.")
    about_mission_desc1_en = models.TextField(default="We believe that continuous and open peer evaluation is the main driver of team development. Often, feedback in companies is forgotten, left only for annual reviews, or kept anonymous, which hinders constructive dialogue.", blank=True)
    about_mission_desc2 = models.TextField(default="Mūsų platforma sprendžia šią problemą siūlydama patogų, vardinį ir struktūrizuotą atsiliepimų rinkimo procesą, kurį papildo modernus dirbtinis intelektas (AI), išryškinantis esmines stiprybes bei pastangas.")
    about_mission_desc2_en = models.TextField(default="Our platform solves this problem by offering a convenient, named, and structured feedback collection process, complemented by modern artificial intelligence (AI) that highlights essential strengths and efforts.", blank=True)
    about_values_title = models.CharField(max_length=255, default="Mūsų Vertybės")
    about_values_title_en = models.CharField(max_length=255, default="Our Values", blank=True)
    about_values_subtitle = models.CharField(max_length=255, default="Principai, kuriais vadovaujamės kurdami platformą")
    about_values_subtitle_en = models.CharField(max_length=255, default="Principles that guide us in building the platform", blank=True)
    about_value1_title = models.CharField(max_length=255, default="Skaidrumas")
    about_value1_title_en = models.CharField(max_length=255, default="Transparency", blank=True)
    about_value1_desc = models.TextField(default="Mes nesislepiame už anonimiškumo. Tikime, kad tikras tobulėjimas prasideda nuo atviro ir nuoširdaus grįžtamojo ryšio.")
    about_value1_desc_en = models.TextField(default="We do not hide behind anonymity. We believe that real improvement starts with open and honest feedback.", blank=True)
    about_value2_title = models.CharField(max_length=255, default="Inovacijos")
    about_value2_title_en = models.CharField(max_length=255, default="Innovation", blank=True)
    about_value2_desc = models.TextField(default="AI integracija leidžia sutaupyti valandas laiko analizuojant dešimtis komentarų, paverčiant juos aiškiomis įžvalgomis.")
    about_value2_desc_en = models.TextField(default="AI integration saves hours of time analyzing dozens of comments, turning them into clear insights.", blank=True)
    about_value3_title = models.CharField(max_length=255, default="Paprastumas")
    about_value3_title_en = models.CharField(max_length=255, default="Simplicity", blank=True)
    about_value3_desc = models.TextField(default="Platforma sukurta taip, kad prašyti ir suteikti grįžtamąjį ryšį užtruktų vos kelis paspaudimus.")
    about_value3_desc_en = models.TextField(default="The platform is designed so that requesting and providing feedback takes just a few clicks.", blank=True)
    about_value4_title = models.CharField(max_length=255, default="Palaikymas")
    about_value4_title_en = models.CharField(max_length=255, default="Support", blank=True)
    about_value4_desc = models.TextField(default="Mūsų tikslas ne kritikuoti, o auginti. Viskas orientuota į komandos nario stiprybių ugdymą.")
    about_value4_desc_en = models.TextField(default="Our goal is not to criticize, but to grow. Everything is focused on developing the team member's strengths.", blank=True)

    # saugumas.html
    security_content = models.TextField(default="""<h2>Mūsų saugumo praktikos</h2><p>Čia pateikiama informacija apie tai, kaip saugome jūsų duomenis.</p>""")
    security_content_en = models.TextField(default="""<h2>Our Security Practices</h2><p>Here is information on how we protect your data.</p>""", blank=True)

    class Meta:
        verbose_name_plural = "Page Descriptions"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(PageDescription, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class EmailTemplate(models.Model):
    """Singleton model for admin-configurable email notification texts."""

    # Gauta nauja apklausa – laiškas vartotojui, kuris gaus feedbacką
    new_survey_subject = models.CharField(
        max_length=255,
        default="Jums priskirta nauja apklausa",
        help_text="El. laiško tema, kai vartotojui priskiriama nauja apklausa."
    )
    new_survey_body = models.TextField(
        default="Sveiki,\n\nJums buvo priskirta nauja apklausa. Prašome prisijungti prie OrbiGrow platformos ir užpildyti apklausą.\n\nPagarbiai,\nOrbiGrow komanda",
        help_text="El. laiško tekstas, siunčiamas vartotojui, kai jam priskiriama nauja apklausa."
    )

    # Gautas prašymas apklausai – laiškas vartotojui, kai gaunamas prašymas
    survey_request_subject = models.CharField(
        max_length=255,
        default="Gautas naujas prašymas užpildyti apklausą",
        help_text="El. laiško tema, kai gaunamas prašymas užpildyti apklausą."
    )
    survey_request_body = models.TextField(
        default="Sveiki,\n\nGavote naują prašymą užpildyti apklausą. Prašome prisijungti prie OrbiGrow platformos ir peržiūrėti prašymą.\n\nPagarbiai,\nOrbiGrow komanda",
        help_text="El. laiško tekstas, siunčiamas vartotojui, kai gaunamas prašymas apklausai."
    )

    # Gautas įvertinimas – laiškas vartotojui, kai kažkas užpildo atsiliepimą apie jį
    feedback_received_subject = models.CharField(
        max_length=255,
        default="Gavote naują įvertinimą",
        help_text="El. laiško tema, kai darbuotojas gauna įvertinimą."
    )
    feedback_received_body = models.TextField(
        default="Sveiki, {vardas}!\n\nJūsų kolega {vertintojas} pateikė atsiliepimą apie jus.\nPrisijunkite prie OrbiGrow platformos ir peržiūrėkite gautą grįžtamąjį ryšį.\n\nPagarbiai,\nOrbiGrow komanda",
        help_text="El. laiško tekstas, siunčiamas darbuotojui, kai jis gauna įvertinimą."
    )

    class Meta:
        verbose_name = "Email Template"
        verbose_name_plural = "Email Templates"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(EmailTemplate, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "El. laiškų šablonai"

