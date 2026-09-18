from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Company(models.Model):
    name = models.CharField(max_length=255)
    email_domain = models.CharField(
        max_length=255, blank=True, default='',
        help_text="El. pašto domenas (pvz. orbigrow.lt). Vartotojai su šiuo domenu bus automatiškai priskirti šiai įmonei."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def get_current_month_ai_queries_count(self):
        from django.utils import timezone
        now = timezone.now()
        return self.ai_usage_logs.filter(timestamp__year=now.year, timestamp__month=now.month).count()

    def get_current_month_ai_cost(self):
        from django.utils import timezone
        from django.db.models import Sum
        now = timezone.now()
        total = self.ai_usage_logs.filter(timestamp__year=now.year, timestamp__month=now.month).aggregate(Sum('total_cost'))['total_cost__sum']
        return total or 0.0

    def get_top_ai_users(self, limit=3):
        from django.db.models import Count
        return self.ai_usage_logs.values('user__first_name', 'user__last_name', 'user__username').annotate(query_count=Count('id')).order_by('-query_count')[:limit]

class Department(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_departments')
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_departments')

    def __str__(self):
        return f"{self.name} ({self.company.name})"

import os
import uuid
import logging

logger = logging.getLogger(__name__)

def user_profile_pic_path(instance, filename):
    unique_suffix = uuid.uuid4().hex[:8]
    return f"profile_pics/{instance.user_id}_{unique_suffix}.jpg"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(default='default.jpg', upload_to=user_profile_pic_path)
    
    # Naujas ryšys su Company modeliu
    company_link = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True) 
    
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='subordinates')
    is_company_admin = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.user.username} Profile'

    def save(self, *args, **kwargs):
        # Jei atnaujinama nuotrauka, ištriname seną nuotrauką iš disko (išskyrus default.jpg)
        if self.pk:
            try:
                old_profile = Profile.objects.filter(pk=self.pk).first()
                if old_profile and old_profile.image and old_profile.image.name != 'default.jpg' and old_profile.image.name != self.image.name:
                    if hasattr(old_profile.image, 'path') and os.path.exists(old_profile.image.path):
                        os.remove(old_profile.image.path)
            except Exception as e:
                logger.warning("Nepavyko ištrinti senos profilio nuotraukos: %s", e)

        super().save(*args, **kwargs)

        # Apdorojame ir suspaudžiame įkeltą nuotrauką
        if self.image and self.image.name and self.image.name != 'default.jpg':
            try:
                if hasattr(self.image, 'path') and os.path.exists(self.image.path):
                    from PIL import Image, ImageOps
                    img = Image.open(self.image.path)

                    # Sutvarkome EXIF orientaciją (iš telefonų kamerų)
                    img = ImageOps.exif_transpose(img)

                    # Konvertuojame į RGB (jei RGBA, LA, P ar kiti formatai)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        bg = Image.new('RGB', img.size, (255, 255, 255))
                        if 'A' in img.getbands():
                            bg.paste(img, mask=img.split()[-1])
                        else:
                            bg.paste(img)
                        img = bg
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')

                    # Sumažiname maksimalų dydį iki 400x400 su aukštos kokybės LANCZOS filtru
                    max_size = (400, 400)
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)

                    # Išsaugome optimizuotą JPEG su 85% kokybe (failo dydis sumažėja iki ~20-40 KB)
                    img.save(self.image.path, format='JPEG', quality=85, optimize=True)
            except Exception as e:
                logger.warning("Klaida apdorojant profilio nuotrauką: %s", e)


class ContractSettings(models.Model):
    """Sutarties nustatymai: kaina ir minimalus mokestis įmonei.
    Viena įmonė gali turėti kelias sutartis (skirtingi laikotarpiai).
    """
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='contracts'
    )
    price_per_employee = models.DecimalField(
        max_digits=8, decimal_places=2,
        help_text="Kaina už vieną aktyvų darbuotoją per mėnesį (EUR)"
    )
    minimum_fee = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0.00'),
        help_text="Minimalus mėnesinis mokestis (EUR)"
    )
    contract_start = models.DateField(help_text="Sutarties pradžios data")
    contract_end = models.DateField(
        null=True, blank=True, help_text="Sutarties pabaigos data (palikite tuščią jei neterminuota)"
    )

    def __str__(self):
        return f"{self.company.name} sutarties nustatymai"

    class Meta:
        verbose_name = "Sutarties nustatymai"
        verbose_name_plural = "Sutarčių nustatymai"


class EmployeeCountLog(models.Model):
    """
    Aktyvių darbuotojų skaičiaus momentinis įrašas.
    Naujas įrašas sukuriamas kaskart, kai darbuotojas pridedamas
    arba aktyvumo statusas pasikeičia (per signalą).
    """
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='employee_count_logs'
    )
    recorded_at = models.DateTimeField(
        default=timezone.now, help_text="Kada buvo užfiksuotas šis skaičius"
    )
    active_count = models.PositiveIntegerField(
        help_text="Aktyvių darbuotojų skaičius tuo metu"
    )

    def __str__(self):
        return f"{self.company.name} – {self.active_count} ({self.recorded_at:%Y-%m-%d %H:%M})"

    class Meta:
        ordering = ['-recorded_at']
        verbose_name = "Darbuotojų skaičiaus įrašas"
        verbose_name_plural = "Darbuotojų skaičiaus įrašai"