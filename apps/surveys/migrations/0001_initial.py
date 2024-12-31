# Generated by Django 5.0.10 on 2024-12-30 20:08

import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('beamlines', '0002_initial'),
        ('dynforms', '0001_initial'),
        ('proposals', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Feedback',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('details', models.JSONField(blank=True, default=dict, editable=False, null=True)),
                ('is_complete', models.BooleanField(default=False)),
                ('beamline', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='feedback', to='beamlines.facility')),
                ('cycle', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='feedback', to='proposals.reviewcycle')),
                ('form_type', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='dynforms.formtype')),
            ],
            options={
                'ordering': ['beamline__acronym'],
            },
        ),
    ]
