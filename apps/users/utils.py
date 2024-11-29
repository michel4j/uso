
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from model_utils import Choices

from . import models


def uso_role_choices(extra_choices=[]):
    from beamlines.models import Facility
    role_choices = [
                       ('user', 'User'),
                       ('reviewer', 'Reviewer'),
                       ('contractor', 'Contractor'),
                   ] + [
                       ('beamteam-member:{}'.format(f.acronym.lower()), '{} BeamTeam Member'.format(f.acronym))
                       for f in
                       Facility.objects.exclude(kind__in=[Facility.TYPES.village, Facility.TYPES.equipment]).exclude(
                           parent__kind=Facility.TYPES.sector
                       ).distinct()
                   ] + extra_choices
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


def send_reset(user):
    from django.urls import reverse
    from notifier import notify
    link = models.SecureLink.objects.create(user=user)
    data = {
        'name': user.first_name,
        'reset_url': "{}{}".format(
            getattr(settings, 'SITE_URL', ""), reverse('password-reset', kwargs={'hash': link.hash})
        ),
    }
    recipients = [user]
    if user.alt_email:
        recipients.append(user.alt_email)
    notify.send(recipients, 'auto-password-reset', context=data)
