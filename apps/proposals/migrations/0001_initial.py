# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2017-01-10 13:40


from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import misc.fields
import model_utils.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CallType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False,
                                                                verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False,
                                                                      verbose_name='modified')),
                ('start_month', models.IntegerField(default=7)),
                ('end_month', models.IntegerField(default=12)),
                ('open_week', models.IntegerField(default=5)),
                ('close_week', models.IntegerField(default=9)),
                ('acronym', models.CharField(blank=True, max_length=10, null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ConfigItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False,
                                                                verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False,
                                                                      verbose_name='modified')),
                ('state', models.CharField(
                    choices=[('design', 'Design'), ('construction', 'Construction'), ('commissioning', 'Commissioning'),
                             ('operating', 'Active')], default='operating', max_length=30)),
            ],
        ),
        migrations.CreateModel(
            name='FacilityConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False,
                                                                verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False,
                                                                      verbose_name='modified')),
                ('accept', models.BooleanField(default=False, verbose_name='Accept Proposals')),
                ('comments', models.TextField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-cycle'],
                'get_latest_by': 'cycle',
                'verbose_name': 'Facility Configuration',
            },
        ),
        migrations.CreateModel(
            name='Proposal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False,
                                                                verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False,
                                                                      verbose_name='modified')),
                ('details', misc.fields.JSONField(blank=True, default={}, editable=False, null=True)),
                ('is_complete', models.BooleanField(default=False)),
                ('leader_username', models.CharField(blank=True, max_length=50, null=True)),
                ('delegate_username', models.CharField(blank=True, max_length=50, null=True)),
                ('title', models.TextField(null=True)),
                ('keywords', models.TextField(null=True)),
                ('team', misc.fields.StringListField(blank=True, null=True)),
                ('state', models.IntegerField(choices=[(0, 'Not Submitted'), (1, 'Submitted')], default=0)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False,
                                                                verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False,
                                                                      verbose_name='modified')),
                ('details', misc.fields.JSONField(blank=True, default={}, editable=False, null=True)),
                ('is_complete', models.BooleanField(default=False)),
                ('role', models.CharField(blank=True, max_length=100, null=True)),
                ('state', models.IntegerField(choices=[(0, 'Pending'), (1, 'Open'), (2, 'Submitted'), (3, 'Closed')],
                                              default=0)),
                ('score', models.IntegerField(default=0)),
                ('due_date', models.DateField(null=True)),
                ('kind', models.CharField(
                    choices=[('scientific', 'Scientific Review'), ('technical', 'Technical Review'),
                             ('safety', 'Safety Review'), ('ethics', 'Ethics Review'),
                             ('equipment', 'Equipment Review'), ('approval', 'Safety Approval')], default='scientific',
                    max_length=30, verbose_name='Type')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ReviewCycle',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False,
                                                                verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False,
                                                                      verbose_name='modified')),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('open_date', models.DateField(verbose_name='Call Open Date')),
                ('close_date', models.DateField(verbose_name='Call Close Date')),
                ('spec_date', models.DateField(verbose_name='Specification Date')),
                ('due_date', models.DateField(null=True, verbose_name='Reviews Due')),
                ('state', models.SmallIntegerField(
                    choices=[(0, 'Call Pending'), (1, 'Call Open'), (2, 'Review'), (3, 'Evaluation'), (4, 'Scheduling'),
                             (5, 'Active'), (6, 'Archived')], default=0)),
            ],
            options={
                'get_latest_by': 'open_date',
            },
        ),
        migrations.CreateModel(
            name='Reviewer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False,
                                                                verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False,
                                                                      verbose_name='modified')),
                ('karma', models.DecimalField(decimal_places=2, default='0.0', max_digits=4)),
                ('comments', models.TextField(blank=True, null=True)),
                ('active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ('user__last_name',),
            },
        ),
        migrations.CreateModel(
            name='ReviewTrack',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False,
                                                                verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False,
                                                                      verbose_name='modified')),
                ('name', models.CharField(max_length=128)),
                ('acronym', models.CharField(max_length=10, unique=True)),
                ('description', models.TextField(null=True)),
                ('special', models.NullBooleanField(default=None, unique=True, verbose_name='Special Requests')),
                ('min_reviewers', models.IntegerField(default=0, verbose_name='Min Reviews/Proposal')),
                ('max_proposals', models.IntegerField(default=0, verbose_name='Max Proposals/Reviewer')),
                ('notify_offset', models.IntegerField(default=1, verbose_name='Notification Delay (days)')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ScoreAdjustment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False,
                                                                verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False,
                                                                      verbose_name='modified')),
                ('reason', models.TextField()),
                ('value',
                 models.FloatField(choices=[(-1, '-1.0'), (-0.5, '-0.5'), (0.5, '+0.5'), (1, '+1.0')], default=0.5)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Submission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False,
                                                                verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False,
                                                                      verbose_name='modified')),
                ('kind', models.CharField(
                    choices=[('user', 'User Access'), ('staff', 'Staff Access'), ('purchased', 'Purchased Access'),
                             ('beamteam', 'Beam Team'), ('education', 'Education/Outreach')], default='user',
                    max_length=20, verbose_name='Access Type')),
                ('state', models.IntegerField(choices=[(0, 'Pending'), (1, 'Started'), (2, 'Reviewed')], default=0)),
                ('comments', models.TextField(blank=True)),
                ('cycle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions',
                                            to='proposals.ReviewCycle')),
                ('proposal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions',
                                               to='proposals.Proposal')),
            ],
        ),
        migrations.CreateModel(
            name='Technique',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False,
                                                                verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False,
                                                                      verbose_name='modified')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True, null=True)),
                ('category', models.CharField(
                    choices=[('diffraction', 'Diffraction/Scattering'), ('imaging', 'Imaging/Microscopy'),
                             ('spectroscopy', 'Spectroscopy'), ('other', 'Other')], default='other', max_length=50,
                    verbose_name='Category')),
                ('acronym', models.CharField(blank=True, max_length=20, null=True, verbose_name='Acronym')),
            ],
            options={
                'ordering': ['category'],
            },
        ),
    ]