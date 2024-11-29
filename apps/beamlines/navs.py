from django.urls import reverse

from misc.navigation import BaseNav, RawNav


class Beamlines(BaseNav):
    label = 'Facilities'
    icon = 'bi-buildings'
    weight = 15
    url = reverse('beamline-list')

    def sub_menu(self, request):
        from beamlines import models
        submenu = super().sub_menu(request)
        separator = True
        for bl in models.Facility.objects.filter(kind__in=['beamline', 'sector']).exclude(
                parent__kind='sector'
        ).order_by('acronym'):
            submenu.append(
                RawNav(
                    label=bl.acronym,
                    roles=self.roles,
                    separator=separator,
                    url=reverse('facility-detail', kwargs={'pk': bl.pk}),
                )
            )
            separator = False

        return submenu


class List(BaseNav):
    parent = Beamlines
    label = 'All Facilities'
    url = reverse('beamline-list')


class Labs(BaseNav):
    parent = Beamlines
    label = 'Laboratories'
    url = reverse('lab-list')
