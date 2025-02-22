# Generated by Django 5.0.10 on 2024-12-30 20:08

import django.db.models.deletion
import django.utils.timezone
import misc.fields
import misc.models
import model_utils.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Attachment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('object_id', models.PositiveIntegerField()),
                ('description', models.CharField(max_length=100, verbose_name='name')),
                ('file', misc.fields.RestrictedFileField(help_text='Maximum size 2.5\xa0MB, Formats: PDF,JPEG,PNG.', storage=misc.fields.LocalStorage(), upload_to=misc.models.attachment_file, verbose_name='Attachment')),
                ('slug', models.SlugField(blank=True, unique=True)),
                ('kind', models.CharField(choices=[('scientific', 'Scientific'), ('safety', 'Safety'), ('ethics', 'Ethics'), ('other', 'Other')], max_length=20, verbose_name='Type')),
                ('is_editable', models.BooleanField(default=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Clarification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('object_id', models.PositiveIntegerField()),
                ('question', models.TextField()),
                ('response', models.TextField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-created'],
            },
        ),
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('object_id', models.PositiveIntegerField()),
                ('user_name', models.CharField(max_length=60, verbose_name='User name')),
                ('address', models.GenericIPAddressField(verbose_name='IP Address')),
                ('kind', models.CharField(choices=[('task', 'Task Performed'), ('create', 'Created'), ('modify', 'Modified'), ('delete', 'Deleted')], max_length=20, verbose_name='Type')),
                ('object_repr', models.CharField(blank=True, max_length=200, null=True, verbose_name='Entity')),
                ('description', models.TextField(blank=True)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
            ],
            options={
                'ordering': ('-created',),
            },
        ),
    ]
