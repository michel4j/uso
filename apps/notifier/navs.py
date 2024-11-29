from django.urls import reverse

from misc.navigation import BaseNav


class Notifications(BaseNav):
    label = 'Notifications'
    parent = 'users.Home'
    styles = "visible-xs"
    url = reverse('notification-list')


class AllNotifications(BaseNav):
    parent = 'users.People'
    label = 'Notifications'
    roles = ['administrator:uso', ]
    separator = True
    url = reverse('admin-notification-list')


class MessageTypes(BaseNav):
    parent = 'users.People'
    label = 'Message Templates'
    roles = ['administrator:uso', ]
    url = reverse('template-list')