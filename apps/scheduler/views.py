import calendar
import collections
from datetime import timedelta, date

from dateutil import parser
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.generic import detail, edit, TemplateView, View
from itemlist.views import ItemListView
from rest_framework import generics, status, permissions
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from misc.views import ConfirmDetailView
from roleperms.views import RolePermsViewMixin
from . import forms
from . import models
from . import serializers
from . import utils

STATES = models.Schedule.STATES


def _fmt_states(state, obj=None):
    return {
        STATES.draft: mark_safe(f'<span class="text-muted"><i class="bi-calendar-week icon-fw"></i> {STATES[state]}</span>'),
        STATES.tentative: mark_safe(f'<span class="text-info"><i class="bi-calendar-check icon-fw"></i> {STATES[state]}</span>'),
        STATES.live: mark_safe(f'<span class="text-success"><i class="bi-calendar-heart icon-fw"></i> {STATES[state]}</span>'),
    }.get(state, state)


class ScheduleListView(RolePermsViewMixin, ItemListView):
    queryset = models.Schedule.objects.all()
    template_name = "item-list.html"
    paginate_by = 15
    allowed_roles = ["administrator:uso"]
    link_url = 'schedule-modes-edit'
    list_filters = ['start_date', 'end_date', 'state']
    list_columns = ['description', 'state', 'config', 'state', 'start_date', 'end_date']
    list_search = ['description', 'state', 'start_date', 'end_date']
    list_transforms = {'state': _fmt_states}
    ordering = ['-start_date', '-state']


class Calendar(RolePermsViewMixin, TemplateView):
    template_name = "scheduler/calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        cur_date = self.kwargs.get(
            'month', date(int(self.kwargs.get('year', today.year)), today.month, today.day).isoformat()
        )
        schedule = models.Schedule.objects.filter(
            start_date__lte=cur_date, end_date__gte=cur_date, state__in=['live', 'tentative']
        ).first()
        if not schedule:
            schedule = models.Schedule.objects.filter(
                start_date__lte=cur_date, end_date__gte=cur_date, state__in=['draft']
            ).first()

        config = schedule.config
        shifts = config.shifts()
        context['default_view'] = 'cycleshift'
        context['view_choices'] = 'cycleshift,monthshift,weekshift'
        context['default_date'] = cur_date
        context['today'] = timezone.now().date()
        context['timezone'] = settings.TIME_ZONE
        context['shift_duration'] = config.duration
        context['shift_minutes'] = config.duration * 60
        context['shift_starts'] = [shift['time'] for shift in shifts]
        context['shifts'] = shifts
        context['shift_count'] = len(context['shift_starts'])
        context['mode_types'] = [{'code': k, 'name': v} for k, v in models.Mode.TYPES]
        context['subtitle'] = 'Current Schedule'
        context['show_year'] = True
        context['event_sources'] = [reverse('facility-modes-api'), ]
        return context


class EventEditor(RolePermsViewMixin, detail.DetailView):
    template_name = "scheduler/editor.html"
    selector_template = None
    model = models.Schedule
    allowed_roles = ['administrator:uso']
    admin_roles = ['administrator:uso']
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
        if not self.kwargs.get('date'):
            today = timezone.now().date()
            if context['schedule'].end_date < today or context['schedule'].start_date > today:
                show_date = context['schedule'].start_date
            else:
                show_date = today
            cur_date = show_date.isoformat()
        else:
            cur_date = self.kwargs.get('date')
        context['default_date'] = cur_date
        context['today'] = timezone.now().date()
        context['default_view'] = 'monthshift'
        context['timezone'] = settings.TIME_ZONE
        context['mode_types'] = [{'code': k, 'name': v} for k, v in models.Mode.TYPES]
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
        stats = collections.defaultdict(float)
        for event in self.get_queryset().with_shifts():
            stats[getattr(event, self.group_by)] += event.shifts
        return JsonResponse(
            [{
                'id': k, 'count': v
            } for k, v in list(stats.items())], safe=False
        )


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
    #permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    parser_classes = (JSONParser,)

    def get_queryset(self, *args, **kwargs):
        queryset = models.Mode.objects.filter(
            schedule__state__in=[models.Schedule.STATES.live, models.Schedule.STATES.tentative]
        )
        if self.request.GET.get('start') and self.request.GET.get('end'):
            start = self.request.GET.get('start')
            end = self.request.GET.get('end')
        else:
            start = timezone.now().date().replace(day=1)
            end = start + timedelta(days=calendar.monthrange(start.year, start.month)[1])
        return queryset.filter(start__lte=end, end__gte=start).all()


class EventUpdateAPI(generics.ListCreateAPIView):
    model = models.Event
    serializer_class = None
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    parser_classes = (JSONParser,)
    creation_key = 'id'
    allowed_schedule_states = [models.Schedule.STATES.live]

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
            'start': parser.parse(info['start']), 'end': parser.parse(info['end']), 'kind': info['kind'], 'tags': info.get('tags', []),
            'comments': info.get('comments', '')
        }


class CreateSchedule(RolePermsViewMixin, edit.CreateView):
    template_name = 'forms/modal.html'
    form_class = forms.ScheduleForm
    model = models.Schedule
    reference_model = None

    def get_success_url(self):
        return self.request.get_full_path()

    def get_reference(self, queryset=None):
        if self.reference_model:
            self.reference = self.reference_model.objects.get(pk=self.kwargs.get('pk'))
            return self.reference
        else:
            raise ValueError('Reference Model Not Provided')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        reference = self.get_reference()
        initial['content_type'] = ContentType.objects.get_for_model(reference)
        initial['object_id'] = reference.pk
        initial['config'] = models.ShiftConfig.objects.order_by('modified').last()
        return initial

    def form_valid(self, form):
        super().form_valid(form)
        return JsonResponse(
            {
                "url": ""
            }
        )


class PromoteSchedule(RolePermsViewMixin, ConfirmDetailView):
    model = models.Schedule
    template_name = "scheduler/forms/switch.html"
    allowed_roles = ["administrator:uso"]

    def get_context_data(self, **kwargs):
        STATE_INDEX = {models.Schedule.STATES.draft: 0, models.Schedule.STATES.tentative: 1, self.model.STATES.live: 2}
        context = super().get_context_data(**kwargs)
        context['state'] = self.kwargs.get('state')
        context['action'] = 'promote' if STATE_INDEX.get(self.object.state) < STATE_INDEX.get(
            self.kwargs.get('state')
        ) else 'demote'
        return context

    def confirmed(self, *args, **kwargs):
        obj = self.get_object()
        if self.kwargs.get('state') in models.Schedule.STATES:
            obj.state = self.kwargs.get('state')
            obj.save()

        return JsonResponse(
            {
                "url": ""
            }
        )


class YearTemplate(RolePermsViewMixin, TemplateView):
    template_name = "scheduler/year.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        slot = int(self.kwargs.get('slot', 8))
        config = models.ShiftConfig.objects.filter(duration=slot).order_by('modified').last()
        shifts = config.shifts()

        context['mode_types'] = [{'code': k, 'name': v} for k, v in models.Mode.TYPES]
        context['shift_duration'] = "{}".format(timedelta(hours=config.duration)).zfill(8)
        context['shift_minutes'] = config.duration * 60
        context['shift_starts'] = [shift['time'] for shift in shifts]
        context['shifts'] = shifts
        context['shift_count'] = len(context['shift_starts'])

        year = int(self.request.GET.get('year', timezone.now().year))
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

        date_str = self.request.GET.get('date', '')
        if date_str:
            d = parser.parse(date_str).date()
        else:
            d = timezone.now().date()

        slot = int(self.kwargs.get('slot', 8))
        config = models.ShiftConfig.objects.filter(duration=slot).order_by('modified').last()
        shifts = config.shifts()

        cycle_start = (d.month // 7 * 6) + 1
        cycle_end = (d.month // 7 * 6) + 7
        cal = calendar.Calendar(calendar.SUNDAY)
        context['mode_types'] = [{'code': k, 'name': v} for k, v in models.Mode.TYPES]
        context['shifts'] = shifts
        context['shift_count'] = len(shifts)
        context['headers'] = [calendar.day_abbr[x][0].upper() for x in cal.iterweekdays()]
        context['months'] = [{
            'name': calendar.month_name[m], 'weeks': cal.monthdatescalendar(d.year, m), 'index': m
        } for m in range(cycle_start, cycle_end)]
        context['current'] = utils.round_time(timezone.localtime(timezone.now()), timedelta(hours=config.duration))
        return context


class MonthTemplate(TemplateView):
    template_name = "scheduler/month.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date_str = self.request.GET.get('date', '')
        if date_str:
            d = parser.parse(date_str).date()
        else:
            d = timezone.now().date()

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
        context['current'] = utils.round_time(timezone.localtime(timezone.now()), timedelta(hours=config.duration))
        return context


class WeekTemplate(TemplateView):
    template_name = "scheduler/week.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date_str = self.request.GET.get('date', '')
        sections = self.request.GET.get('sections', '').split(',')
        if date_str:
            d = parser.parse(date_str).date()
        else:
            d = timezone.now().date()
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
        context['current'] = utils.round_time(timezone.localtime(timezone.now()), timedelta(hours=config.duration))
        return context


class ModeStatsAPI(EventStatsAPI):
    model = models.Mode
    group_by = 'kind'
