from django.db import models
from django.db.models.functions import Round
from django.utils.translation import gettext as _
from model_utils import Choices
from model_utils.models import TimeStampedModel, TimeFramedModel
from misc.utils import Struct
from django.db.models import Q, F, Sum
from misc.functions import Hours, Shifts
from misc.models import DateSpanMixin
from django.conf import settings
from django.utils import timezone
from datetime import timedelta, datetime, date
from misc.models import GenericContentMixin


User = getattr(settings, "AUTH_USER_MODEL")


class ShiftConfig(TimeStampedModel):
    start = models.TimeField()
    duration = models.IntegerField(default=8)
    number = models.IntegerField(default=3)
    names = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.start.strftime('%X')}-{self.duration}HRS x {self.number}"

    def shifts(self):
        labels = self.names.split(',')
        dt = timezone.now().replace(hour=self.start.hour, minute=self.start.minute)
        starts = [dt + timedelta(hours=x * self.duration) for x in range(self.number)]
        info = [
            {
                'label': label,
                'description': start.strftime('%H:%M'),
                'start': start.isoformat(),
                'time': start.strftime('%H')
            } for label, start in zip(labels, starts)
            if start
        ]
        return info


class Schedule(TimeStampedModel, DateSpanMixin):
    STATES = Choices(
        ('draft', _('Draft')),
        ('tentative', _('Tentative')),
        ('live', _('Live')),
    )
    description = models.CharField(max_length=255)
    state = models.CharField(max_length=20, choices=STATES, default=STATES.draft)
    config = models.ForeignKey(ShiftConfig, related_name='schedules', verbose_name='Shift Configuration', on_delete=models.CASCADE)

    def is_editable(self):
        return self.state in [self.STATES.draft, self.STATES.tentative]

    def mode_stats(self):
        raw_stats = self.modes.all().with_shifts().values('kind__acronym').order_by('kind__acronym').annotate(
            count=Sum('shifts')
        )
        return {
            item['kind__acronym']: item['count']
            for item in raw_stats
        }

    def normal_shifts(self):
        data = self.modes.filter(kind__is_normal=True).with_shifts().aggregate(total=Sum('shifts'))
        return data.get('total', 0) or 0

    def __str__(self):
        return f"{self.description} [{self.state}]"


class EventQuerySet(models.QuerySet):
    def active(self, dt=None):
        dt = timezone.now()
        return self.filter(
            (Q(start__isnull=True) | Q(start__lte=dt)) & (Q(end__isnull=True) | Q(end__gte=dt)))

    @staticmethod
    def _clean_event(event):
        event = event if not isinstance(event, dict) else Struct(**event)
        current_timezone = timezone.get_current_timezone()
        if isinstance(event.start, date):
            event.start = datetime.combine(event.start, datetime.min.time(), tzinfo=current_timezone)
        if isinstance(event.end, date):
            event.end = datetime.combine(event.end, datetime.min.time(), tzinfo=current_timezone)
        return event

    def expired(self, dt=None):
        dt = timezone.now() if not dt else dt
        return self.filter(Q(end__isnull=False) & Q(end__lt=dt))

    def pending(self, dt=None):
        dt = timezone.now() if not dt else dt
        return self.filter(Q(start__gt=dt))

    def next(self, dt=None):
        dt = timezone.now() if not dt else dt
        return self.filter(start__gt=dt).order_by('start').first()

    def prev(self, dt=None):
        """Return the next instance by start_date"""
        dt = timezone.now() if not dt else dt
        return self.filter(start__lt=dt).order_by('-start').first()

    def relevant(self, extras=None):
        extras = {} if not extras else extras
        yesterday = timezone.now() - timedelta(days=7)
        return self.filter(start__gte=yesterday, start__lte=timezone.now() + timedelta(days=7), **extras)

    def with_duration(self):
        return self.annotate(
            duration=Round(Hours(F('end'), F('end'), output_field=models.FloatField()), 2)
        )

    def with_hours(self):
        return self.annotate(
            hours=Round(Hours(F('end'), F('start'), output_field=models.FloatField()), 2)
        )

    def with_shifts(self):
        return self.annotate(
            shifts=Round(Shifts(F('end'), F('start'), output_field=models.FloatField()), 1)
        )

    def ends_before(self, event):
        event = self._clean_event(event)
        return self.filter(end__lt=event.start)

    def ends_after(self, event):
        event = self._clean_event(event)
        return self.filter(end__gt=event.end)

    def starts_before(self, event):
        event = self._clean_event(event)
        return self.filter(start__lt=event.start)

    def starts_after(self, event):
        event = self._clean_event(event)
        return self.filter(start__gt=event.end)

    def within(self, event):
        event = self._clean_event(event)
        return self.filter(start__gte=event.start, end__lte=event.end)

    def matches(self, event):
        event = self._clean_event(event)
        return self.filter(start=event.start, end=event.end)

    def starts_with(self, event):
        event = self._clean_event(event)
        return self.filter(start=event.start)

    def ends_with(self, event):
        event = self._clean_event(event)
        return self.filter(end=event.end)

    def starts_within(self, event):
        event = self._clean_event(event)
        return self.filter(start__gte=event.start, start__lt=event.end)

    def ends_within(self, event):
        event = self._clean_event(event)
        return self.filter(end__gt=event.start, end__lte=event.end)

    def encloses(self, event):
        event = self._clean_event(event)
        return self.filter(start__lt=event.start, end__gt=event.end)

    def intersects(self, event):
        event = self._clean_event(event)
        return self.filter(
            Q(start__gte=event.start, start__lte=event.end) |
            Q(end__gt=event.start, end__lte=event.end) |
            Q(start__lte=event.start, end__gte=event.end)
        )


class Event(TimeStampedModel, TimeFramedModel):
    cancelled = models.BooleanField(default=False)
    objects = EventQuerySet.as_manager()
    schedule = models.ForeignKey(Schedule, related_name='%(class)ss', on_delete=models.CASCADE)
    comments = models.TextField(null=True, blank=True, default="")

    class Meta:
        abstract = True


class ModeTag(TimeStampedModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class ModeType(TimeStampedModel):
    acronym = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=10, blank=True, null=True)
    active = models.BooleanField(default=True)
    is_normal = models.BooleanField(default=False, help_text="Is this a normal mode? (e.g., work shift)")

    def __str__(self):
        return self.acronym


class Mode(Event):
    kind = models.ForeignKey(ModeType, related_name='modes', on_delete=models.PROTECT)
    tags = models.ManyToManyField(ModeTag, blank=True)
    objects = EventQuerySet.as_manager()

    def __str__(self):
        return f"{self.kind}: {self.start}-{self.end}"

    class Meta:
        unique_together = [('schedule', 'start', 'end')]
