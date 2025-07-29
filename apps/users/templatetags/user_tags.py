from django import template

from users import models

register = template.Library()


def get_field_choices(choice_type):
    """
    Get the choices and values for the Choices class.
    """
    return{
        'choices': [choice[-1] for choice in choice_type],
        'values': [choice[-1] for choice in choice_type]
    }


@register.simple_tag(takes_context=True)
def set_sector_choices(context):
    context['field'].update(get_field_choices(models.Institution.SECTORS))
    return models.Institution.SECTORS


@register.simple_tag(takes_context=True)
def set_student_choices(context):
    context['field'].update(get_field_choices(models.User.STUDENTS))
    return models.User.STUDENTS


@register.simple_tag(takes_context=True)
def set_staff_choices(context):
    context['field'].update(get_field_choices(models.User.STAFF))
    return models.User.STAFF


@register.filter(name="get_institution")
def get_institution(email):
    user = models.User.objects.filter(email__iexact=email.lower()).first()
    return user and f"{user.get_classification_display()} {user.institution}"
