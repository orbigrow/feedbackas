from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from .models import Profile

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['image']

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size'):
            # Max 10MB
            if image.size > 10 * 1024 * 1024:
                raise forms.ValidationError("Nuotraukos failas per didelis (maksimalus dydis: 10 MB).")
            # Verify valid image
            try:
                from PIL import Image
                # Make sure file pointer is preserved
                initial_pos = image.tell() if hasattr(image, 'tell') else 0
                img = Image.open(image)
                img.verify()
                if hasattr(image, 'seek'):
                    image.seek(initial_pos)
            except Exception:
                raise forms.ValidationError("Netinkamas paveikslėlio formatas. Prašome pasirinkti JPG, PNG ar kitą palaikomą formatą.")
        return image

class CustomPasswordChangeForm(PasswordChangeForm):
    """Password change form with custom styling support."""
    pass
