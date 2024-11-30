# Generated by Django 5.0.9 on 2024-11-30 21:18

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('beamlines', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='usersupport',
            name='staff',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='support', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='usersupport',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='support', to='beamlines.facilitytag'),
        ),
        migrations.AlterUniqueTogether(
            name='labworkspace',
            unique_together={('lab', 'name')},
        ),
        migrations.AlterUniqueTogether(
            name='usersupport',
            unique_together={('staff', 'facility', 'start')},
        ),
    ]
