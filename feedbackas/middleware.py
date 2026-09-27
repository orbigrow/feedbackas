from django.shortcuts import redirect
from django.urls import reverse
from users.models import Profile, Company
from django.utils import translation
class ForceLanguageMiddleware:
    """
    Jei kalbų pasirinkimas išjungtas, priverstinai nustato lietuvių kalbą ('lt')
    visiems vartotojams.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            from feedbackas.models import GlobalSettings
            settings = GlobalSettings.load()
            if not settings.language_switcher_enabled:
                translation.activate('lt')
                request.LANGUAGE_CODE = 'lt'
        except Exception:
            pass
            
        response = self.get_response(request)
        return response


class CompanyRequiredMiddleware:
    """
    Middleware tikrina ar prisijungęs vartotojas turi priskirtą įmonę.
    Jei neturi ir domenas nesusietas su jokia įmone – nukreipia į pranešimo puslapį.
    Superuseriai ir tam tikri URL (login, logout, admin, static ir t.t.) leidžiami be apribojimų.
    """

    # URL prefiksai, kuriuos leidžiama pasiekti be įmonės
    EXEMPT_URLS = [
        '/login/',
        '/logout/',
        '/register/',
        '/admin/',
        '/orbigrow-admin-panel/',
        '/accounts/',
        '/superadmin/',
        '/no-company/',
        '/set-language/',
        '/i18n/',
        '/static/',
        '/media/',
        '/apie-mus/',
        '/saugumas/',
        '/privatumo-politika/',
        '/tinklarastis/',
        '/favicon.ico',
        '/',  # index landing page
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Tik autentifikuotiems vartotojams
        if request.user.is_authenticated:
            # Superuseriai – visada leisti
            if request.user.is_superuser:
                return self.get_response(request)

            # Tikrinti ar URL yra exempt
            path = request.path
            # Leisti landing page tik tiksliai '/'
            if path == '/':
                return self.get_response(request)

            for exempt in self.EXEMPT_URLS:
                if exempt != '/' and path.startswith(exempt):
                    return self.get_response(request)

            # Tikrinti ar vartotojas turi įmonę
            try:
                profile = request.user.profile
                if profile.company_link is not None:
                    return self.get_response(request)
            except Profile.DoesNotExist:
                pass

            # Vartotojas neturi įmonės – nukreipti į pranešimo puslapį
            return redirect('no_company')

        return self.get_response(request)

class SecurityHeadersMiddleware:
    """
    Middleware skirtas pašalinti nereikalingas antraštes (Server, X-Powered-By),
    kad nebūtų atskleidžiamos Django/Python ar kitos technologijų versijos.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Pašalinti antraštes, jei jos buvo pridėtos anksčiau Django lygyje
        if 'Server' in response:
            del response['Server']
        if 'X-Powered-By' in response:
            del response['X-Powered-By']
            
        return response

class RestrictHttpMethodMiddleware:
    """
    Middleware skirtas blokuoti nepageidaujamus HTTP metodus (TRACE, PUT, DELETE ir pan.).
    Leidžiami tik standartiniai ir saugūs GET, POST, HEAD, OPTIONS metodai.
    """
    ALLOWED_METHODS = ['GET', 'POST', 'HEAD', 'OPTIONS']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in self.ALLOWED_METHODS:
            from django.http import HttpResponseNotAllowed
            return HttpResponseNotAllowed(self.ALLOWED_METHODS)
            
        return self.get_response(request)
