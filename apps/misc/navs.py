from django.conf import settings
from django.urls import reverse

from misc.navigation import BaseNav, RawNav

USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ['admin:uso'])


class Admin(BaseNav):
    label = 'Admin'
    icon = 'bi-gear'
    weight = 200
    roles = USO_ADMIN_ROLES


class FormDesigner(BaseNav):
    parent = Admin
    label = 'Form Designer'
    roles = USO_ADMIN_ROLES
    url = reverse('dynforms-list')


class ReportBuilder(BaseNav):
    parent = Admin
    label = 'Report Builder'
    roles = USO_ADMIN_ROLES
    url = reverse('report-editor-root')
