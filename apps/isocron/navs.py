from django.urls import reverse
from django.conf import settings
from misc.navigation import BaseNav


USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ['admin:uso'])


class Tasks(BaseNav):
    parent = 'misc.Admin'
    label = 'Background Tasks'
    separator = True
    roles = USO_ADMIN_ROLES
    url = reverse('task-list')

