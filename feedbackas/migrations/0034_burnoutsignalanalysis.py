from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('feedbackas', '0033_wellbeingcheckin_engagement_meaning_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='BurnoutSignalAnalysis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fingerprint', models.CharField(db_index=True, max_length=64)),
                ('risk_level', models.CharField(default='low', max_length=20)),
                ('source', models.CharField(choices=[('ai', 'AI'), ('rules', 'Taisyklės')], default='ai', max_length=10)),
                ('result', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='burnout_signal_analyses', to='users.company')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='burnout_signal_analyses', to=settings.AUTH_USER_MODEL)),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='requested_burnout_analyses', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Perdegimo signalų analizė',
                'verbose_name_plural': 'Perdegimo signalų analizės',
                'ordering': ['-created_at'],
            },
        ),
    ]
