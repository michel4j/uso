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


class ReportIndex(BaseNav):
    label = 'Reports'
    icon = 'bi-file-earmark-richtext'
    weight = 180
    roles = USO_ADMIN_ROLES

    def sub_menu(self, request):
        from reportcraft.models import Report
        sections = set(Report.objects.values_list('section', flat=True))
        submenu = super().sub_menu(request)
        separator = True
        for section in sections:
            if not section:
                section = 'general'
            if section and not section.strip():
                continue
            submenu.append(
                RawNav(
                    label=section.title() or 'General',
                    roles=self.roles,
                    separator=separator,
                    url=reverse('report-section-index', kwargs={'section': section}),
                )
            )
            separator = False

        return submenu


class ReportBuilder(BaseNav):
    parent = ReportIndex
    label = 'Report Builder'
    roles = USO_ADMIN_ROLES
    url = reverse('report-editor-root')
