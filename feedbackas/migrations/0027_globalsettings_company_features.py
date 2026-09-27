from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        ('feedbackas', '0026_blogpost'),
    ]

    operations = [
        migrations.AlterField(
            model_name='globalsettings',
            name='personal_form_enabled',
            field=models.BooleanField(default=True, help_text="Bendrai įjungti 'Individuali forma' funkcionalumą."),
        ),
        migrations.AlterField(
            model_name='globalsettings',
            name='team_form_enabled',
            field=models.BooleanField(default=True, help_text="Bendrai įjungti 'Komandinė forma' funkcionalumą."),
        ),
        migrations.AddField(
            model_name='globalsettings',
            name='personal_form_all_companies',
            field=models.BooleanField(default=True, help_text="Taikyti 'Individuali forma' visoms įmonėms."),
        ),
        migrations.AddField(
            model_name='globalsettings',
            name='personal_form_companies',
            field=models.ManyToManyField(blank=True, related_name='personal_form_settings', to='users.company'),
        ),
        migrations.AddField(
            model_name='globalsettings',
            name='team_form_all_companies',
            field=models.BooleanField(default=True, help_text="Taikyti 'Komandinė forma' visoms įmonėms."),
        ),
        migrations.AddField(
            model_name='globalsettings',
            name='team_form_companies',
            field=models.ManyToManyField(blank=True, related_name='team_form_settings', to='users.company'),
        ),
    ]
