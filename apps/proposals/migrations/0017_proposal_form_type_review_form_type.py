# Generated by Django 5.0.9 on 2024-11-30 06:49

import django.db.models.deletion
from django.db import migrations, models


def transfer_formspec_data(apps, schema_editor):
    Proposal = apps.get_model("proposals", "Proposal")
    Review = apps.get_model("proposals", "Review")
    db_alias = schema_editor.connection.alias
    for p in Proposal.objects.using(db_alias).all():
        p.form_type = p.spec.form_type
        p.save()
    for r in Review.objects.using(db_alias).all():
        r.form_type = r.spec.form_type
        r.save()


class Migration(migrations.Migration):

    dependencies = [
        ('dynforms', '0005_alter_formtype_options_dynentry_form_type_and_more'),
        ('proposals', '0016_alter_proposal_details_alter_review_details'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposal',
            name='form_type',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='dynforms.formtype'),
        ),
        migrations.AddField(
            model_name='review',
            name='form_type',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='dynforms.formtype'),
        ),
        migrations.RunPython(transfer_formspec_data),
    ]
