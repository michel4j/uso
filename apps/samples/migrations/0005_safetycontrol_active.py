# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2017-02-07 17:59


from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('samples', '0004_safetypermission_review'),
    ]

    operations = [
        migrations.AddField(
            model_name='safetycontrol',
            name='active',
            field=models.BooleanField(default=True, verbose_name='Show in Review'),
        ),
    ]