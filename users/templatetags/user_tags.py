from django import template
from users.models import Profile

register = template.Library()

@register.filter
def user_avatar(user):
    try:
        if hasattr(user, 'profile'):
            if user.profile.image and user.profile.image.name and user.profile.image.name != 'default.jpg':
                return user.profile.image.url
    except Profile.DoesNotExist:
        Profile.objects.create(user=user)
    except Exception:
        pass
    
    # Return an inline SVG data URI with a person silhouette
    return "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'%3E%3Crect width='80' height='80' rx='40' fill='%23e2e8f0'/%3E%3Ccircle cx='40' cy='30' r='13' fill='%2394a3b8'/%3E%3Cellipse cx='40' cy='68' rx='22' ry='18' fill='%2394a3b8'/%3E%3C/svg%3E"
