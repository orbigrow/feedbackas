from .models import GlobalSettings, PageDescription

def global_settings_processor(request):
    try:
        settings = GlobalSettings.load()
    except Exception:
        settings = None
    try:
        page_description = PageDescription.load()
    except Exception:
        page_description = None
    return {
        'global_settings': settings,
        'page_description': page_description,
    }
