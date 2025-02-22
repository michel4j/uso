# Generated by Django 5.0.10 on 2024-12-30 20:08

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('publications', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='publication',
            name='users',
            field=models.ManyToManyField(blank=True, related_name='publications', to=settings.AUTH_USER_MODEL, verbose_name='CLS Users'),
        ),
        migrations.AddField(
            model_name='publication',
            name='funders',
            field=models.ManyToManyField(blank=True, related_name='publications', to='publications.fundingsource', verbose_name='Funding Sources'),
        ),
        migrations.AddField(
            model_name='publication',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='publications', to='publications.publicationtag', verbose_name='Tags'),
        ),
        migrations.AddField(
            model_name='subjectarea',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sub_areas', to='publications.subjectarea'),
        ),
        migrations.AddField(
            model_name='publication',
            name='areas',
            field=models.ManyToManyField(blank=True, related_name='publications', to='publications.subjectarea', verbose_name='Subject Areas'),
        ),
        migrations.AddField(
            model_name='article',
            name='journal',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='articles', to='publications.journal'),
        ),
        migrations.AddField(
            model_name='pdbdeposition',
            name='reference',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pdbs', to='publications.publication'),
        ),
    ]
