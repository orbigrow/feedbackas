from django import template
from users.models import Profile

register = template.Library()

DEFAULT_AVATAR_SVG = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'%3E%3Crect width='80' height='80' rx='40' fill='%23e2e8f0'/%3E%3Ccircle cx='40' cy='30' r='13' fill='%2394a3b8'/%3E%3Cellipse cx='40' cy='68' rx='22' ry='18' fill='%2394a3b8'/%3E%3C/svg%3E"

def _get_profile(user_or_profile):
    if not user_or_profile:
        return None
    if hasattr(user_or_profile, 'profile'):
        try:
            return user_or_profile.profile
        except Profile.DoesNotExist:
            return Profile.objects.create(user=user_or_profile)
        except Exception:
            return None
    elif hasattr(user_or_profile, 'image'):
        return user_or_profile
    return None

@register.filter
def user_avatar(user_or_profile):
    """
    Grąžina vartotojo profilio nuotraukos URL.
    Jei nuotrauka neįkelta arba yra numatytoji, grąžina SVG siluetą.
    """
    profile = _get_profile(user_or_profile)
    if profile and profile.image and profile.image.name and profile.image.name != 'default.jpg':
        try:
            return profile.image.url
        except Exception:
            pass
    return DEFAULT_AVATAR_SVG

@register.filter
def has_avatar(user_or_profile):
    """
    Patikrina, ar vartotojas turi įkeltą individualią profilio nuotrauką.
    """
    profile = _get_profile(user_or_profile)
    if profile and profile.image and profile.image.name and profile.image.name != 'default.jpg':
        return True
    return False
