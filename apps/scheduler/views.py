import calendar
import collections
from datetime import timedelta, date, datetime

from crisp_modals.views import ModalConfirmView, ModalCreateView, ModalUpdateView, ModalDeleteView
from dateutil import parser
from django.conf import settings
from django.db.models import Sum
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.timezone import make_aware
from django.views.generic import detail, TemplateView, View
from itemlist.views import ItemListView
from rest_framework import generics, status, permissions
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from misc.utils import debug_value
from roleperms.views import RolePermsViewMixin
from . import models, forms
from . import serializers
from . import utils

STATES = models.Schedule.STATES
USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ["admin:uso"])


def _fmt_states(state, obj=None):
    return {
        STATES.draft: mark_safe(f'<span class="text-body-secondary"><i class="bi-calendar-week icon-fw"></i> {STATES[state]}</span>'),
        STATES.tentative: mark_safe(f'<span class="text-info"><i class="bi-calendar-check icon-fw"></i> {STATES[state]}</span>'),
        STATES.live: mark_safe(f'<span class="text-success"><i class="bi-calendar-heart icon-fw"></i> {STATES[state]}</span>'),
    }.get(state, state)


def parse_date(date_str: str) -> datetime:
    """
    Parse a date string into a timezone date for the local time. Returns the current date if the string is empty or invalid.
    :param date_str: the date string to parse
    """
    now = timezone.localtime(timezone.now())
    if not date_str:
        return now
    try:
        dt = make_aware(parser.parse(date_str), timezone=timezone.get_current_timezone())
        return dt
    except ValueError:
        return now


class ScheduleListView(RolePermsViewMixin, ItemListView):
    model = models.Schedule
    template_name = "item-list.html"
    paginate_by = 15
    allowed_roles = USO_ADMIN_ROLES
    link_url = 'schedule-modes-edit'
    list_filters = ['start_date', 'end_date', 'state']
    list_columns = ['description', 'state', 'config', 'state', 'start_date', 'end_date']
    list_search = ['description', 'state', 'start_date', 'end_date']
    list_transforms = {'state': _fmt_states}
    ordering = ['-start_date', '-state']


class ModeTypeList(RolePermsViewMixin, ItemListView):
    model = models.ModeType
    template_name = "tooled-item-list.html"
    tool_template = "scheduler/mode-type-tools.html"
    paginate_by = 15
    allowed_roles = USO_ADMIN_ROLES
    link_url = 'edit-mode-type'
    link_attr = 'data-modal-url'
    list_filters = ['active', 'is_normal', 'created', 'modified']
    list_columns = ['name', 'acronym', 'color', 'description', 'active', 'is_normal']
    list_search = ['acronym', 'name', 'description']
    list_transforms = {
        'active': lambda x, obj: mark_safe('<i class="bi-check2 icon-fw"></i>') if x else '',
        'is_normal': lambda x, obj: mark_safe('<i class="bi-check2 icon-fw"></i>') if x else '',
        'color': lambda x, obj: mark_safe(f'<span class="badge" style="background-color: {x};">&nbsp;</span>'),
    }


class AddModeType(RolePermsViewMixin, ModalCreateView):
    model = models.ModeType
    form_class = forms.ModeTypeForm
    allowed_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        return reverse('mode-type-list')


class EditModeType(RolePermsViewMixin, ModalUpdateView):
    model = models.ModeType
    form_class = forms.ModeTypeForm
    allowed_roles = USO_ADMIN_ROLES

    def get_delete_url(self):
        return reverse('delete-mode-type', kwargs={'pk': self.object.pk})

    def get_success_url(self):
        return reverse('mode-type-list')


class DeleteModeType(RolePermsViewMixin,  ModalDeleteView):
    model = models.ModeType
    allowed_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        return reverse('mode-type-list')


class Calendar(RolePermsViewMixin, TemplateView):
    template_name = "scheduler/calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localtime(timezone.now()).date()
        cur_date = self.kwargs.get(
            'month', date(int(self.kwargs.get('year', today.year)), today.month, today.day).isoformat()
        )
        schedule = models.Schedule.objects.filter(
            start_date__lte=cur_date, end_date__gte=cur_date, state__in=['live', 'tentative']
        ).first()
        if not schedule:
            schedule = models.Schedule.objects.filter(start_date__gt=cur_date).first()

        config = schedule.config
        shifts = config.shifts()
        context['default_view'] = 'cycleshift'
        context['view_choices'] = 'cycleshift,monthshift,weekshift'
        context['default_date'] = cur_date
        context['today'] = today
        context['timezone'] = settings.TIME_ZONE
        context['shift_duration'] = config.duration
        context['shift_minutes'] = config.duration * 60
        context['shift_starts'] = [shift['time'] for shift in shifts]
        context['shifts'] = shifts
        context['shift_count'] = len(context['shift_starts'])
        context['mode_types'] = models.ModeType.objects.all()
        context['subtitle'] = 'Current Schedule'
        context['show_year'] = True
        context['event_sources'] = [reverse('facility-modes-api'), ]
        return context


class EventEditor(RolePermsViewMixin, detail.DetailView):
    template_name = "scheduler/editor.html"
    selector_template = None
    model = models.Schedule
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES
    editor_type = 'event'
    allow_reservations = False

    def get_object(self, queryset=None):
        self.schedule = super().get_object(queryset=queryset)
        return self.schedule

    def get_api_urls(self):
        return {
            'api': "", 'events': [], 'stats': ""
        }

    def get_shift_config(self):
        return self.schedule.config

    def get_tags(self):
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localtime(timezone.now()).date()

        if not self.kwargs.get('date'):
            if context['schedule'].end_date < today or context['schedule'].start_date > today:
                show_date = context['schedule'].start_date
            else:
                show_date = today
            cur_date = show_date.isoformat()
        else:
            cur_date = self.kwargs.get('date')
        context['default_date'] = cur_date
        context['today'] = today
        context['default_view'] = 'monthshift'
        context['timezone'] = settings.TIME_ZONE
        context['mode_types'] = models.ModeType.objects.filter(active=True)
        context['subtitle'] = context['schedule'].description

        config = self.get_shift_config()
        shifts = config.shifts()

        context['shift_duration'] = config.duration
        context['shift_minutes'] = config.duration * 60
        context['shift_starts'] = [shift['time'] for shift in shifts]
        context['shifts'] = shifts
        context['shift_count'] = len(context['shift_starts'])

        context['api_urls'] = self.get_api_urls()
        context['tag_types'] = self.get_tags()
        context['editor_type'] = self.editor_type
        return context


class EventStatsAPI(RolePermsViewMixin, View):
    model = models.Event
    queryset = None
    group_by = 'kind'

    def get_queryset(self, *args, **kwargs):
        if not self.queryset:
            self.queryset = self.model.objects.filter()
        return self.queryset.filter(schedule__pk=self.kwargs['pk']).all()

    def get(self, request, *args, **kwargs):
        raw_stats = self.get_queryset().with_shifts().values(self.group_by).order_by(self.group_by).annotate(
            count=Sum('shifts')
        )
        return JsonResponse([
            {'id': item[self.group_by], 'count': item['count']}
            for item in raw_stats
        ], safe=False)


class ModeEditor(EventEditor):
    selector_template = "scheduler/mode-selector.html"
    editor_type = 'mode'

    def get_api_urls(self):
        url = reverse('schedule-modes-api', kwargs={'pk': self.schedule.pk})
        return {
            'api': url, 'events': [url], 'stats': reverse('mode-stats-api', kwargs={'pk': self.schedule.pk})
        }

    def get_tags(self):
        return models.ModeTag.objects.filter()


class FacilityModeListAPI(generics.ListAPIView):
    model = models.Mode
    serializer_class = serializers.ModeSerializer
    parser_classes = (JSONParser,)

    def get_queryset(self, *args, **kwargs):
        queryset = models.Mode.objects.filter(
            schedule__state__in=[models.Schedule.STATES.live, models.Schedule.STATES.tentative]
        )
        today = timezone.localtime(timezone.now()).date()
        if self.request.GET.get('start') and self.request.GET.get('end'):
            start = timezone.make_aware(parser.parse(self.request.GET.get('start')))
            end = timezone.make_aware(parser.parse(self.request.GET.get('end')))
        else:
            start = today.replace(day=1)
            end = start + timedelta(days=calendar.monthrange(start.year, start.month)[1])
        return queryset.filter(start__lte=end, end__gte=start).all()


class EventUpdateAPI(generics.ListCreateAPIView):
    model = models.Event
    serializer_class = None
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    parser_classes = (JSONParser,)
    creation_key = 'id'
    allowed_schedule_states = [models.Schedule.STATES.live, models.Schedule.STATES.tentative]

    def get_queryset(self, *args, **kwargs):
        self.schedule = models.Schedule.objects.filter(pk=self.kwargs['pk']).first()
        if self.request.GET.get('start') and self.request.GET.get('end'):
            start = self.request.GET.get('start')
            end = self.request.GET.get('end')
        else:
            start = self.schedule.start_date
            end = self.schedule.end_date
        self.queryset = self.model.objects.filter(schedule=self.schedule, start__lte=end, end__gte=start)
        return self.queryset

    def post_process(self, schedule, queryset, data):
        pass

    def get_data(self, info):
        return {
            'start': parser.parse(info['start']), 'end': parser.parse(info['end']), 'comments': info.get('comments', ''),
            'tags': info.get('tags', []),
        }

    def handle_one(self, request, queryset, data):
        pk = request.data.get('id')
        output_status = status.HTTP_304_NOT_MODIFIED
        if pk:  # cancelling or deleting or comments:
            if request.data.get('delete'):
                queryset.filter(pk=pk).delete()
            elif request.data.get('cancel'):
                queryset.filter(pk=pk).update(cancelled=True)
            elif request.data.get('reset'):
                queryset.filter(pk=pk).update(cancelled=False)
            elif request.data.get('comments'):
                queryset.filter(pk=pk).update(comments=request.data.get('comments'))
            output_status = status.HTTP_200_OK
        elif data.get(self.creation_key):
            output_status = utils.create_event(self.schedule, queryset, data)
            self.post_process(self.schedule, queryset, data)
        elif request.data.get('cancel'):
            output_status = utils.cancel_event(self.schedule, queryset, data)
        elif request.data.get('delete'):
            output_status = utils.clear_event(self.schedule, queryset, data)
        elif request.data.get('placeholder'):
            output_status = utils.create_event(self.schedule, queryset, data)  # placeholders
        return output_status

    def create(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if self.schedule.state not in self.allowed_schedule_states:
            return Response([], status=status.HTTP_304_NOT_MODIFIED)  # Can't add beamtime to draft schedule
        output_status = status.HTTP_304_NOT_MODIFIED
        if isinstance(request.data, dict):
            data = self.get_data(request.data)
            output_status = self.handle_one(request, queryset, data)
        elif isinstance(request.data, collections.MutableSequence):
            outputs = []
            for info in request.data:
                data = self.get_data(info)
                output_status = self.handle_one(request, queryset, data)
                outputs.append(output_status)
            output_status = max(outputs)
        return Response([], status=output_status)


class ModeListAPI(EventUpdateAPI):
    model = models.Mode
    serializer_class = serializers.ModeSerializer
    creation_key = 'kind'
    allowed_schedule_states = [models.Schedule.STATES.draft, models.Schedule.STATES.tentative]

    def get_data(self, info):
        return {
            'start': parser.parse(info['start']),
            'end': parser.parse(info['end']),
            'kind': models.ModeType.objects.filter(pk=info['kind']).first(),
            'tags': info.get('tags', []),
            'comments': info.get('comments', '')
        }


class PromoteSchedule(RolePermsViewMixin, ModalConfirmView):
    model = models.Schedule
    template_name = "scheduler/forms/switch.html"
    allowed_roles = USO_ADMIN_ROLES

    def get_context_data(self, **kwargs):
        state_index = {models.Schedule.STATES.draft: 0, models.Schedule.STATES.tentative: 1, self.model.STATES.live: 2}
        context = super().get_context_data(**kwargs)
        context['state'] = self.kwargs.get('state')
        context['action'] = 'promote' if state_index.get(self.object.state) < state_index.get(
            self.kwargs.get('state')
        ) else 'demote'
        return context

    def confirmed(self, *args, **kwargs):
        obj = self.get_object()
        if self.kwargs.get('state') in models.Schedule.STATES:
            obj.state = self.kwargs.get('state')
            obj.save()
        return JsonResponse({"url": ""})


class YearTemplate(RolePermsViewMixin, TemplateView):
    template_name = "scheduler/year.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        slot = int(self.kwargs.get('slot', 8))
        config = models.ShiftConfig.objects.filter(duration=slot).order_by('modified').last()
        shifts = config.shifts()

        context['mode_types'] = models.ModeType.objects.all()
        context['shift_duration'] = f"{timedelta(hours=config.duration)}".zfill(8)
        context['shift_minutes'] = config.duration * 60
        context['shift_starts'] = [shift['time'] for shift in shifts]
        context['shifts'] = shifts
        context['shift_count'] = len(context['shift_starts'])

        today = timezone.localtime(timezone.now()).date()
        year = int(self.request.GET.get('year', today.year))
        cal = calendar.Calendar(6)
        context['year'] = year
        max_width = 1 + max([(r[0] % 6) + r[1] for r in [calendar.monthrange(year, m) for m in range(1, 13)]])
        context['months'] = [{
            'name': calendar.month_abbr[m], 'first': timezone.datetime(year, m, 1),
            'dates': [d for i, d in enumerate(cal.itermonthdates(year, m)) if i < max_width], 'index': m
        } for m in range(1, 13)]
        for month in context['months']:
            width = len(month['dates'])
            if width < max_width:
                month['dates'].extend(
                    [month['dates'][-1] + timedelta(days=x) for x in range(1, 1 + max_width - width)]
                )
        context['columns'] = list(range(max_width))
        return context


class CycleTemplate(RolePermsViewMixin, TemplateView):
    template_name = "scheduler/cycle.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime(timezone.now())
        date_str = self.request.GET.get('date', '')
        if date_str:
            d = parser.parse(date_str).date()
        else:
            d = now.date()

        slot = int(self.kwargs.get('slot', 8))
        config = models.ShiftConfig.objects.filter(duration=slot).order_by('modified').last()
        shifts = config.shifts()

        cycle_start = (d.month // 7 * 6) + 1
        cycle_end = (d.month // 7 * 6) + 7
        cal = calendar.Calendar(calendar.SUNDAY)
        context['mode_types'] = models.ModeType.objects.all()
        context['shifts'] = shifts
        context['shift_count'] = len(shifts)
        context['headers'] = [calendar.day_abbr[x][0].upper() for x in cal.iterweekdays()]
        context['months'] = [{
            'name': calendar.month_name[m], 'weeks': cal.monthdatescalendar(d.year, m), 'index': m
        } for m in range(cycle_start, cycle_end)]
        context['current'] = utils.round_time(now, timedelta(hours=config.duration))
        return context


class MonthTemplate(TemplateView):
    template_name = "scheduler/month.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date_str = self.request.GET.get('date', '')
        now = timezone.localtime(timezone.now())
        if date_str:
            d = parser.parse(date_str).date()
        else:
            d = now.date()

        if 'start' in self.request.GET and 'end' in self.request.GET:
            context['range_start'] = parser.parse(self.request.GET.get('start')).date()
            context['range_end'] = parser.parse(self.request.GET.get('end')).date()

        slot = int(self.kwargs.get('slot', 8))
        config = models.ShiftConfig.objects.filter(duration=slot).order_by('modified').last()
        shifts = config.shifts()

        cal = calendar.Calendar(calendar.SUNDAY)
        dates = [[calendar.day_abbr[x] for x in cal.iterweekdays()]] + cal.monthdatescalendar(d.year, d.month)
        context['month'] = {'num': d.month, 'name': d.strftime('%M'), 'dates': [list(x) for x in zip(*dates)]}
        context['headers'] = ['Week {}'.format(d.isocalendar()[1]) for d in context['month']['dates'][1][1:]]
        context['shifts'] = shifts
        context['shift_count'] = len(shifts)
        context['current'] = utils.round_time(now, timedelta(hours=config.duration))
        return context


class WeekTemplate(TemplateView):
    template_name = "scheduler/week.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date_str = self.request.GET.get('date', '')
        sections = self.request.GET.get('sections', '').split(',')
        now = timezone.localtime(timezone.now())
        if date_str:
            d = parser.parse(date_str).date()
        else:
            d = now.date()
        cal = calendar.Calendar(calendar.SUNDAY)
        names = [calendar.day_abbr[x] for x in cal.iterweekdays()]
        dates = [x for x in cal.monthdatescalendar(d.year, d.month) if d in x][0]

        slot = int(self.kwargs.get('slot', 8))
        config = models.ShiftConfig.objects.filter(duration=slot).order_by('modified').last()
        shifts = config.shifts()

        context['week'] = [{'name': nm, 'date': d} for nm, d in zip(names, dates)]
        context['sections'] = sections
        context['shifts'] = shifts
        context['shift_count'] = len(shifts)
        context['current'] = utils.round_time(now, timedelta(hours=config.duration))
        return context


class ModeStatsAPI(EventStatsAPI):
    model = models.Mode
    group_by = 'kind'
