# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2024-11-08 02:43


from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0011_auto_20170213_1226'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reservation',
            name='shifts',
            field=models.PositiveIntegerField(default=0),
        ),
    ]