from django import template

from users import models

register = template.Library()


@register.simple_tag(takes_context=True)
def get_sector_choices(context):
    return models.Institution.SECTORS


@register.simple_tag(takes_context=True)
def get_student_choices(context):
    return models.User.STUDENTS


@register.simple_tag(takes_context=True)
def get_staff_choices(context):
    return models.User.STAFF


@register.filter(name="get_institution")
def get_institution(email):
    user = models.User.objects.filter(email__iexact=email.lower()).first()
    return user and "{0} {1}".format(user.get_classification_display(), user.institution)
