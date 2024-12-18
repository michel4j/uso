from datetime import timedelta

from django.conf import settings
from django.urls import reverse_lazy
from django.utils import timezone

from . import utils
from isocron import BaseCronJob
from notifier import notify


USO_PROFILE_MANAGER = getattr(settings, 'USO_PROFILE_MANAGER', None)


class CleanRegistrations(BaseCronJob):
    run_every = "P1D"

    def do(self):
        num = utils.clear_registrations()
        if num:
            return "{} old registrations removed".format(num)


class SyncStaff(BaseCronJob):
    run_every = "P1D"

    def do(self):
        staff_list = USO_PROFILE_MANAGER.fetch_new_users()
        updated = utils.create_users(staff_list)
        return "{} new staff members saved".format(updated)


class NotifyNewInstitutions(BaseCronJob):
    run_every = "P1D"

    def do(self):
        from . import models
        from users.models import User
        yesterday = timezone.now() - timedelta(days=1)
        new_institutions = models.Institution.objects.filter(modified__gte=yesterday,
                                                             state=models.Institution.STATES.pending)
        pending_institutions = models.Institution.objects.filter(state=models.Institution.STATES.pending)
        if new_institutions.exists():
            data = {
                'new': new_institutions,
                'pending': pending_institutions,
                'url': "{}{}?created__gte={}&state=pending".format(
                    getattr(settings, 'SITE_URL', ""),
                    reverse_lazy('institution-list'),
                    yesterday.date()
                ),
            }
            recipients = User.objects.all_with_roles("contracts-administrator")
            notify.send(recipients, "new-institutions", context=data)

        return "New Institution Notification Sent"
