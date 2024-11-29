from django.contrib import admin
from django.db.models import Count

from misc.filters import FilterFactory


class BeamlineFilterFactory(FilterFactory):
    @classmethod
    def new(cls, field_name='facility'):
        class BeamlineFilter(admin.SimpleListFilter):
            title = "Beamlines"
            parameter_name = 'blspec'

            def lookups(self, request, model_admin):
                from beamlines.models import Facility
                choices = sorted(
                    {
                        v['acronym']
                        for v in Facility.objects.exclude(
                        kind__in=[Facility.TYPES.sector, Facility.TYPES.village, Facility.TYPES.equipment]
                    ).values(
                        'acronym'
                    )
                    }
                )
                sectors = [
                    v for v in
                    Facility.objects.filter(kind__in=[Facility.TYPES.sector, Facility.TYPES.village]).order_by('created')
                ]

                _chlist = [(bl, '{0}'.format(bl)) for bl in choices]
                _chlist += [("-{0}".format(bl.acronym.lower()), '{0}'.format(bl.name)) for bl in sectors]
                _chlist += [('multiple', 'Multiple Beamlines')]
                return _chlist

            def queryset(self, request, queryset):
                if not self.value():
                    return queryset
                elif self.value() == 'multiple':
                    return queryset.annotate(num=Count(field_name)).filter(num__gte=2)
                elif self.value().startswith('-'):
                    flt = {field_name + '__parent__acronym__iexact': self.value()[1:]}
                    return queryset.filter(**flt).distinct()
                else:
                    flt = {field_name + '__acronym__iexact': self.value()}
                    return queryset.filter(**flt).distinct()

        return BeamlineFilter
