# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2017-01-19 13:28


from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('beamlines', '0007_auto_20170117_0945'),
        ('projects', '0007_auto_20170118_2302'),
    ]

    operations = [
        migrations.AddField(
            model_name='labsession',
            name='equipment',
            field=models.ManyToManyField(blank=True, related_name='lab_sessions', to='beamlines.Ancillary'),
        ),
    ]
