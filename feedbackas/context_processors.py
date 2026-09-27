from .models import GlobalSettings, PageDescription


class RequestSettingsProxy:
    """
    Transparent proxy around GlobalSettings that resolves company-specific feature flags
    for the current user/company, while preserving all model attributes and methods.
    """
    def __init__(self, settings, company=None, is_superuser=False):
        self._settings = settings
        self.company = company
        self.is_superuser = is_superuser

    @property
    def personal_form_enabled(self):
        if not self._settings:
            return True
        if self.is_superuser:
            return self._settings.personal_form_enabled
        return self._settings.is_personal_form_enabled_for_company(self.company)

    @property
    def team_form_enabled(self):
        if not self._settings:
            return True
        if self.is_superuser:
            return self._settings.team_form_enabled
        return self._settings.is_team_form_enabled_for_company(self.company)

    @property
    def language_switcher_enabled(self):
        if not self._settings:
            return True
        return self._settings.language_switcher_enabled

    def __getattr__(self, name):
        return getattr(self._settings, name)

    def __bool__(self):
        return bool(self._settings)


def global_settings_processor(request):
    try:
        settings = GlobalSettings.load()
    except Exception:
        settings = None

    try:
        page_description = PageDescription.load()
    except Exception:
        page_description = None

    user = getattr(request, 'user', None)
    company = None
    is_superuser = False
    if user and user.is_authenticated:
        is_superuser = user.is_superuser
        try:
            company = user.profile.company_link
        except Exception:
            company = None

    proxy_settings = RequestSettingsProxy(settings, company=company, is_superuser=is_superuser)

    return {
        'global_settings': proxy_settings,
        'raw_global_settings': settings,
        'page_description': page_description,
    }
