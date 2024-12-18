from django.conf import settings
from django.urls import reverse

from misc.navigation import BaseNav, RawNav

USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ['admin:uso'])


class Forms(BaseNav):
    label = 'Forms'
    icon = 'bi-layout-text-window-reverse'
    weight = 100
    roles = USO_ADMIN_ROLES
    url = reverse('dynforms-list')
    styles = "hidden-xs"

    def allowed(self, request):
        # Only allowed in debug mode
        allowed = super().allowed(request) and settings.DEBUG
        return allowed

    def sub_menu(self, request):
        from dynforms import models
        submenu = super().sub_menu(request)

        for form_type in models.FormType.objects.all():
            submenu.append(RawNav(
                label="{} Form".format(form_type.name),
                roles=self.roles,
                url=reverse('dynforms-builder', kwargs={'pk': form_type.pk}),
            ))
        return submenu
