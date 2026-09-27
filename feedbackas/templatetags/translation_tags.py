from django import template
from django.utils.translation import get_language, gettext_lazy as _

register = template.Library()

@register.filter
def translate_field(obj, field_name):
    """
    Grąžina lauko reikšmę priklausomai nuo aktyvios kalbos.
    Pvz., jei kalba 'en', ieškos '{field_name}_en'.
    Naudojimas šablone: {{ page_description|translate_field:'index_hero_title' }}
    """
    lang = get_language()
    
    if lang == 'en':
        en_field = f"{field_name}_en"
        en_value = getattr(obj, en_field, None)
        if en_value:
            return en_value
            
    # Fallback to default (LT)
    return getattr(obj, field_name, '')

@register.filter
def translate_project(name):
    if not name:
        return ""
        
    translations = {
        'Atsiliepimas': _('Atsiliepimas'),
        'Komandinis darbas': _('Komandinis darbas'),
        'Komunikabilumas': _('Komunikabilumas'),
        'Iniciatyvumas': _('Iniciatyvumas'),
        'Problemų sprendimas': _('Problemų sprendimas'),
        'Lyderystė': _('Lyderystė'),
        'Analitinis mąstymas': _('Analitinis mąstymas'),
        'Kūrybiškumas': _('Kūrybiškumas'),
        'Adaptabilumas': _('Adaptabilumas'),
        'Atsakingumas': _('Atsakingumas'),
        'Laiko planavimas': _('Laiko planavimas'),
        'Techninės žinios': _('Techninės žinios'),
        'Strateginis mąstymas': _('Strateginis mąstymas'),
        'Klientų aptarnavimas': _('Klientų aptarnavimas'),
        'Derybos': _('Derybos'),
        'Prezentavimo įgūdžiai': _('Prezentavimo įgūdžiai'),
        'Patikimumas': _('Patikimumas'),
        'Motyvacija': _('Motyvacija'),
        'Pozityvumas': _('Pozityvumas'),
        'Efektyvumas': _('Efektyvumas'),
        'Savarankiškumas': _('Savarankiškumas'),
    }
    
    return translations.get(name, name)
