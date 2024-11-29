# Generated by Django 5.0.9 on 2024-11-14 03:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publications', '0003_alter_subjectarea_category'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pdbdeposition',
            name='details',
            field=models.JSONField(default=dict),
        ),
        migrations.AlterField(
            model_name='publication',
            name='affiliation',
            field=models.JSONField(default=dict),
        ),
        migrations.AlterField(
            model_name='publication',
            name='history',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
