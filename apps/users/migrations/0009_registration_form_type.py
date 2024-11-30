# Generated by Django 5.0.9 on 2024-11-30 06:49

import django.db.models.deletion
from django.db import migrations, models


def transfer_formspec_data(apps, schema_editor):
    Registration = apps.get_model("users", "Registration")
    db_alias = schema_editor.connection.alias
    for obj in Registration.objects.using(db_alias).all():
        obj.form_type = obj.spec.form_type
        obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('dynforms', '0005_alter_formtype_options_dynentry_form_type_and_more'),
        ('users', '0008_remove_user_cfactor'),
    ]

    operations = [
        migrations.AddField(
            model_name='registration',
            name='form_type',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='dynforms.formtype'),
        ),
        migrations.RunPython(transfer_formspec_data),
    ]
