from django.conf import settings

from misc.navigation import BaseNav
from django.urls import reverse

USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ['admin:uso'])


class Scheduling(BaseNav):
    label = 'Scheduling'
    icon = 'bi-calendar2-range'
    weight = 20


class Current(BaseNav):
    parent = Scheduling
    label = 'Current Schedule'
    url = reverse('schedule-calendar')


class List(BaseNav):
    parent = Scheduling
    label = 'List of Schedules'
    roles = USO_ADMIN_ROLES
    url = reverse('schedule-list')
    styles = "d-none d-sm-inline"