# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2024-11-08 02:43


from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0004_auto_20170119_1112'),
    ]

    operations = [
        migrations.AlterField(
            model_name='institution',
            name='state',
            field=models.CharField(
                choices=[(b'new', 'New'), (b'pending', 'Pending'), (b'started', 'Started'), (b'active', 'Active'),
                         (b'exempt', 'Exempt'), (b'expired', 'Expired')], default=b'new', max_length=20,
                verbose_name=b'Agreement'),
        ),
    ]