# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2017-01-17 15:45


from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('beamlines', '0006_auto_20170117_0720'),
    ]

    operations = [
        migrations.RenameField(
            model_name='ancillary',
            old_name='active',
            new_name='available',
        ),
        migrations.RenameField(
            model_name='lab',
            old_name='active',
            new_name='available',
        ),
        migrations.AddField(
            model_name='labworkspace',
            name='available',
            field=models.BooleanField(default=True),
        ),
    ]
