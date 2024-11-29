# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2017-01-10 13:40


import uuid

import django.utils.timezone
import model_utils.fields
from django.db import migrations, models

import misc.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Acceptance',
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
                ('host', models.GenericIPAddressField(blank=True, null=True)),
                ('active', models.BooleanField(default=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Agreement',
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
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('code', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('state',
                 models.CharField(
                     choices=[('disabled', 'Disabled'), ('enabled', 'Enabled'), ('archived', 'Archived')],
                     default='disabled', max_length=10
                 )),
                ('description', models.TextField(blank=True, verbose_name='Short Description')),
                ('content', models.TextField(blank=True, verbose_name='Agreement Text')),
                ('roles', misc.fields.StringListField(
                    blank=True, help_text='Separate entries with semi-colons',
                    verbose_name='Required for users with these roles'
                )),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
