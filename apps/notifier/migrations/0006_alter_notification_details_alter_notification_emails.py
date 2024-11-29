# Generated by Django 5.0.9 on 2024-11-14 03:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifier', '0005_auto_20241112_2030'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='details',
            field=models.JSONField(blank=True),
        ),
        migrations.AlterField(
            model_name='notification',
            name='emails',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
