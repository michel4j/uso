from django import template

from agreements import models

register = template.Library()


@register.filter(name="active_agreements")
def active_agreements(user):
    return models.Acceptance.objects.filter(user=user, active=True)


@register.filter(name="user_agreements")
def user_agreements(user) -> dict:
    """
    Get active and pending agreements for a user.
    :param user: user
    :return: dictionary with 'accepted' and 'pending' agreements
    """
    return {
        'accepted': models.Agreement.objects.active_for_user(user),
        'pending': models.Agreement.objects.pending_for_user(user)
    }


