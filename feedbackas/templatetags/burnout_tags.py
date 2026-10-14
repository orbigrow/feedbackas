import json

from django import template
from django.utils.safestring import mark_safe

from feedbackas.services.burnout_signals import BURNOUT_CLOUD_KEYWORDS

register = template.Library()


@register.simple_tag
def burnout_keywords_json(enabled=True):
    """Perdegimo signalų raktiniai žodžiai (vienas šaltinis backend'ui ir raktinių žodžių debesiui)."""
    if not enabled:
        return mark_safe('[]')
    # ensure_ascii=True – saugu įterpti tiesiai į <script>
    return mark_safe(json.dumps(BURNOUT_CLOUD_KEYWORDS, ensure_ascii=True).replace('</', '<\\/'))

