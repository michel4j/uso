from django.urls import reverse
from django.conf import settings
from misc.navigation import BaseNav


USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ['admin:uso'])


class Notifications(BaseNav):
    label = 'Notifications'
    parent = 'users.Home'
    styles = "visible-xs"
    url = reverse('notification-list')


class AllNotifications(BaseNav):
    parent = 'users.People'
    label = 'Notifications'
    roles = USO_ADMIN_ROLES
    separator = True
    url = reverse('admin-notification-list')


class MessageTypes(BaseNav):
    parent = 'users.People'
    label = 'Message Templates'
    roles = USO_ADMIN_ROLES
    url = reverse('template-list')