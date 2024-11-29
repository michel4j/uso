import abc
import calendar
import datetime
from datetime import date
from enum import IntEnum
from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class DateLimit(IntEnum):
    LEFT = -1
    RIGHT = 1
    BOTH = 0


class FilterFactory(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def new(cls, *args, **kwargs) -> admin.SimpleListFilter:
        ...


class DateLimitFilterFactory(FilterFactory):

    @classmethod
    def new(cls, model, field_name='date', filter_title='Start date', limit=DateLimit.BOTH):
        class DateLimitListFilter(admin.SimpleListFilter):
            title = filter_title
            parameter_name = '{}{}'.format(
                field_name, {
                    DateLimit.LEFT: '_gte', DateLimit.RIGHT: '_lte'
                }.get(limit, '')
            )

            def lookups(self, request, model_admin):
                choices = sorted(
                    {v[field_name].year for v in model.objects.values(field_name).order_by(field_name).distinct()},
                    reverse=True
                )
                return [(yr, f'{yr}') for yr in choices]

            def queryset(self, request, queryset):
                flt = {}
                if self.value() and limit <= DateLimit.BOTH:
                    dt = date(int(self.value()), 1, 1)
                    flt[field_name + '__gte'] = dt
                if self.value() and limit >= DateLimit.RIGHT:
                    dt = date(int(self.value()), 12, 31)
                    flt[field_name + '__lte'] = dt

                return queryset.filter(**flt)

        return DateLimitListFilter


class YearFilterFactory(FilterFactory):

    @classmethod
    def new(cls, field_name='created', start=None, end=None, reverse=True):
        end = end if end else timezone.now().year
        start = start if start else end - 15

        class YearFilter(admin.SimpleListFilter):
            parameter_name = f'{field_name}_year'
            title = parameter_name.replace('_', ' ').title()

            def lookups(self, request, model_admin):
                choices = range(start, end + 1) if not reverse else reversed(range(start, end + 1))
                return ((yr, f'{yr}') for yr in choices)

            def queryset(self, request, queryset):
                flt = {} if not self.value() else {f'{field_name}__year': self.value()}
                return queryset.filter(**flt)

        return YearFilter


class MonthFilterFactory(FilterFactory):
    @classmethod
    def new(cls, field_name='created'):
        class MonthFilter(admin.SimpleListFilter):
            parameter_name = f'{field_name}_month'
            title = parameter_name.replace('_', ' ').title()

            def lookups(self, request, model_admin):
                return ((month, calendar.month_name[month]) for month in range(1, 13))

            def queryset(self, request, queryset):
                flt = {} if not self.value() else {f'{field_name}__month': self.value()}
                return queryset.filter(**flt)

        return MonthFilter


class QuarterFilterFactory(FilterFactory):
    @classmethod
    def new(cls, field_name='created'):
        class QuarterFilter(admin.SimpleListFilter):
            parameter_name = f'{field_name}_quarter'
            title = parameter_name.replace('_', ' ').title()

            def lookups(self, request, model_admin):
                return ((i + 1, f'Q{i + 1}') for i in range(4))

            def queryset(self, request, queryset):
                flt = {} if not self.value() else {f'{field_name}__quarter': self.value()}
                return queryset.filter(**flt)

        return QuarterFilter


class TimeScaleFilterFactory(FilterFactory):
    @classmethod
    def new(cls):
        class TimeScaleFilter(admin.SimpleListFilter):
            parameter_name = 'time_scale'
            title = parameter_name.replace('_', ' ').title()

            def lookups(self, request, model_admin):
                return (
                    ('month', 'Month'),
                    ('quarter', 'Quarter'),
                    ('cycle', 'Cycle'),
                    ('year', 'Year')
                )

            def queryset(self, request, queryset):
                flt = {}
                return queryset.filter(**flt)

        return TimeScaleFilter


class FutureDateListFilterFactory(FilterFactory):
    @classmethod
    def new(cls, field_name='due_date'):
        class FutureDateListFilter(admin.SimpleListFilter):
            parameter_name = '{}_due'.format(field_name)
            title = field_name.title().replace('_', ' ')

            def lookups(self, request, model_admin):
                return [
                    ('expired', _('Expired')), ('today', _('Today')), ('tomorrow', _('Tomorrow')),
                    ('7days', _('Within 7 days')), ('month', _('This month')), ('year', _('This year')),
                ]

            def queryset(self, request, queryset):
                now = timezone.now()
                # When time zone support is enabled, convert "now" to the user's time
                # zone so Django's definition of "Today" matches what the user expects.
                if timezone.is_aware(now):
                    now = timezone.localtime(now)

                today = now.date()
                tomorrow = today + datetime.timedelta(days=1)
                if today.month == 12:
                    next_month = today.replace(year=today.year + 1, month=1, day=1)
                else:
                    next_month = today.replace(month=today.month + 1, day=1)
                next_year = today.replace(year=today.year + 1, month=1, day=1)

                kwarg_since = f'{field_name}__gte'
                kwarg_until = f'{field_name}__lt'

                if not self.value():
                    query = {}
                elif self.value() == 'expired':
                    query = {kwarg_until: today}
                elif self.value() == 'today':
                    query = {field_name: tomorrow}
                elif self.value() == 'tomorrow':
                    query = {field_name: today}
                elif self.value() == '7days':
                    query = {kwarg_since: today, kwarg_until: today + datetime.timedelta(days=7)}
                elif self.value() == 'month':
                    query = {kwarg_since: today, kwarg_until: next_month}
                elif self.value() == 'year':
                    query = {kwarg_since: today, kwarg_until: next_year}
                else:
                    query = {}
                return queryset.filter(**query)

        return FutureDateListFilter
