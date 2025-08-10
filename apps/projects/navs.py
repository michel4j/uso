from django.urls import reverse
from django.conf import settings

from misc.navigation import BaseNav

USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ["admin:uso"])
USO_STAFF_ROLES = getattr(settings, "USO_STAFF_ROLES", ["staff"])
USO_HSE_ROLES = getattr(settings, "USO_HSE_ROLES", ["staff:hse"])


class Projects(BaseNav):
    label = 'Projects'
    icon = 'bi-briefcase'
    weight = 3
    roles = USO_ADMIN_ROLES + USO_HSE_ROLES
    url = reverse('project-list')


class Permits(BaseNav):
    label = 'Permits'
    icon = 'bi-key'
    weight = 2.5
    roles = USO_STAFF_ROLES


class AllProjects(BaseNav):
    parent = Projects
    label = 'Projects'
    roles = USO_ADMIN_ROLES
    url = reverse('project-list')


class AllMaterials(BaseNav):
    parent = Projects
    label = 'Materials'
    roles = USO_ADMIN_ROLES + USO_HSE_ROLES
    url = reverse('material-list')


class AllSessions(BaseNav):
    parent = Permits
    label = 'Session Permits'
    roles = USO_STAFF_ROLES
    url = reverse('session-list')


class LabPermits(BaseNav):
    label = 'Lab Permits'
    parent = Permits
    roles = USO_STAFF_ROLES
    url = reverse('lab-permit-list')


class UserProjects(BaseNav):
    label = 'My Projects'
    parent = 'users.Home'
    url = reverse('user-project-list')


class UserBeamTime(BaseNav):
    label = 'My Beamtime'
    parent = 'users.Home'
    url = reverse('user-beamtime-list')

