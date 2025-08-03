
from datetime import timedelta
from functools import lru_cache

from django.conf import settings
from django.utils import timezone
from model_utils import Choices

from misc.utils import humanize_role
from . import models

ASSIGNABLE_ROLES = getattr(settings, 'USO_ASSIGNABLE_ROLES', [])


@lru_cache
def uso_role_choices(extra_choices: list = None):
    """
    Returns a Choices object containing the assignable roles in the USO system.
    :param extra_choices:
    :return:
    """
    extra_choices = extra_choices or []

    from beamlines.models import Facility
    roles = {}
    for item in ASSIGNABLE_ROLES:
        if isinstance(item, str):
            roles[item] = humanize_role(item)
        elif isinstance(item, dict) and 'role' in item:
            role = str(item['role'])
            if not item.get('per-facility', False):
                roles[role] = humanize_role(role)
            else:
                for f in Facility.objects.all():
                    for f_role in f.expand_role(role):
                        roles[f_role] = humanize_role(f_role)

    role_choices = list(roles.items()) + extra_choices
    return Choices(*sorted(role_choices))


def clear_registrations():
    min_created_time = timezone.now() - timedelta(days=7)
    deleted = models.Registration.objects.filter(modified__lte=min_created_time).delete()
    return deleted


def create_users(staff):
    updated = 0
    for user_info in staff:
        info = {
            k: v for k, v in user_info.items()
            if k in ['title', 'first_name', 'last_name', 'preferred_name', 'email', 'username', 'roles', 'permissions']
        }
        user, created = models.User.objects.get_or_create(username=info['username'])
        if created:
            models.User.objects.filter(username=user.username).update(**info)
            updated += 1
    return updated


def send_reset(user, template='auto-password-reset'):
    from django.urls import reverse
    from notifier import notify
    link = models.SecureLink.objects.create(user=user)
    data = {
        'name': user.first_name,
        'reset_url': f"{getattr(settings, 'SITE_URL', '')}{reverse('password-reset', kwargs={'hash': link.hash})}",
    }
    recipients = [user]
    if user.alt_email:
        recipients.append(user.alt_email)
    notify.send(recipients, template, context=data)
