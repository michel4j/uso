# Generated by Django 5.0.9 on 2024-11-14 18:01

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('beamlines', '0011_alter_ancillary_details_alter_facility_details_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='facilitytag',
            name='facility',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='beamlines.facility'),
        ),
    ]