from django.urls import reverse
from django.conf import settings
from misc.navigation import BaseNav

USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ['admin:uso'])
USO_HSE_ROLES = getattr(settings, "USO_HSE_ROLES", ['staff:hse'])


class Samples(BaseNav):
    label = 'My Samples'
    parent = 'users.Home'
    url = reverse('user-sample-list')


class Permissions(BaseNav):
    label = 'Safety Permissions'
    parent = 'misc.Admin'
    separator = True
    weight = 60
    url = reverse('safety-permission-list')
    roles = USO_HSE_ROLES + USO_ADMIN_ROLES


class HazardousSubstances(BaseNav):
    label = 'Hazardous Substances'
    parent = 'misc.Admin'
    weight = 61
    url = reverse('hazardous-substance-list')
    roles = USO_HSE_ROLES + USO_ADMIN_ROLES

