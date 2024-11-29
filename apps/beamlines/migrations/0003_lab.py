# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2017-01-11 20:36


import django.utils.timezone
import model_utils.fields
from django.db import migrations, models

import misc.fields


class Migration(migrations.Migration):
    dependencies = [
        ('samples', '0002_auto_20170110_0740'),
        ('beamlines', '0002_auto_20170110_0740'),
    ]

    operations = [
        migrations.CreateModel(
            name='Lab',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(
                    default=django.utils.timezone.now, editable=False,
                    verbose_name='created'
                )),
                ('modified', model_utils.fields.AutoLastModifiedField(
                    default=django.utils.timezone.now, editable=False,
                    verbose_name='modified'
                )),
                ('name', models.CharField(max_length=255, unique=True)),
                ('acronym', models.CharField(max_length=20, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('workspaces', models.IntegerField(default=1, verbose_name=b'Work Spaces')),
                ('admin_roles', misc.fields.StringListField()),
                ('details', misc.fields.JSONField(blank=True, default={}, editable=False)),
                ('permissions', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    to='samples.SafetyPermission'
                )),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
