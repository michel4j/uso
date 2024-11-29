from misc.navigation import BaseNav
from django.urls import reverse


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
    roles = ['administrator:uso']
    url = reverse('schedule-list')
    styles = "hidden-xs"