# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2017-01-19 21:17


from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('proposals', '0009_auto_20170116_1721'),
    ]

    operations = [
        migrations.DeleteModel(
            name='CallType',
        ),
        migrations.AlterField(
            model_name='scoreadjustment',
            name='submission',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='adjustment',
                                       to='proposals.Submission'),
        ),
    ]