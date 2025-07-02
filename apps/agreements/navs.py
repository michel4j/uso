from django.urls import reverse
from django.conf import settings
from misc.navigation import BaseNav


USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ['admin:uso'])
USO_CONTRACTS_ROLES = getattr(settings, "USO_CONTRACTS_ROLES", ['staff:contracts'])


class Agreements(BaseNav):
    parent = 'misc.Admin'
    label = 'Agreements'
    roles = USO_CONTRACTS_ROLES + USO_ADMIN_ROLES
    url = reverse('agreement-list')
