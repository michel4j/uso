from django.contrib import admin

from misc.filters import FilterFactory


class CycleFilterFactory(FilterFactory):

    @classmethod
    def new(cls, field_name='cycle'):

        class CycleFilter(admin.SimpleListFilter):
            title = "Cycle"
            parameter_name = 'cycle'

            def lookups(self, request, model_admin):
                from proposals.models import ReviewCycle
                choices = [
                    (c.pk, f'Cycle {c.pk}: {c}')
                    for c in ReviewCycle.objects.all().order_by('-start_date')
                ]
                return choices

            def queryset(self, request, queryset):
                if not self.value():
                    return queryset
                else:
                    flt = {field_name + '__exact': self.value()}
                    return queryset.filter(**flt).distinct()

        return CycleFilter


class TechniqueFilterFactory(FilterFactory):
        @classmethod
        def new(cls, field_name='configs__techniques'):
            class TechniqueFilter(admin.SimpleListFilter):
                title = "Techniques"
                parameter_name = 'tech'

                def lookups(self, request, model_admin):
                    from proposals.models import Technique
                    choices = sorted({v for v in Technique.objects.filter(category__isnull=True).order_by('name')})
                    choice_list = [(bl.pk, f'{bl}') for bl in choices]
                    for cat in Technique.TYPES:
                        choice_list += [(cat[0], f"[{cat[1]}]")]
                        choice_list += [(bl.pk, f'{bl}') for bl in Technique.objects.filter(category=cat[0])]

                    return choice_list

                def queryset(self, request, queryset):
                    if not self.value():
                        return queryset
                    elif not self.value().isdigit():
                        flt = {f"{field_name}__category": self.value()}
                        return queryset.filter(**flt).distinct()
                    else:
                        flt = {field_name: self.value()}
                        return queryset.filter(**flt).distinct()

            return TechniqueFilter
