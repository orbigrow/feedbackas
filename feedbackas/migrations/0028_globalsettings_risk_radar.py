from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        ('feedbackas', '0027_globalsettings_company_features'),
    ]

    operations = [
        migrations.AddField(
            model_name='globalsettings',
            name='risk_radar_enabled',
            field=models.BooleanField(default=True, help_text="Bendrai įjungti 'Rizikos radaras' (Flight & Burnout) funkcionalumą."),
        ),
        migrations.AddField(
            model_name='globalsettings',
            name='risk_radar_all_companies',
            field=models.BooleanField(default=True, help_text="Taikyti 'Rizikos radaras' visoms įmonėms."),
        ),
        migrations.AddField(
            model_name='globalsettings',
            name='risk_radar_companies',
            field=models.ManyToManyField(blank=True, related_name='risk_radar_settings', to='users.company'),
        ),
    ]
