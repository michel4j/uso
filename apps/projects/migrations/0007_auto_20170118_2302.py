# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2017-01-19 05:02


from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0006_labsession_workspaces'),
    ]

    operations = [
        migrations.AlterField(
            model_name='session',
            name='state',
            field=models.CharField(
                choices=[('ready', 'Ready'), ('live', 'Active'), ('complete', 'Complete'), ('cancelled', 'Cancelled'),
                         ('terminated', 'Terminated')], default='ready', max_length=15),
        ),
    ]