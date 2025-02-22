from django.db import models
from django.utils.translation import gettext as _
from model_utils import Choices
from model_utils.models import TimeStampedModel, TimeFramedModel
from misc.utils import Struct
from django.db.models import Q, F, Sum
from misc.functions import Hours, Shifts
from misc.models import DateSpanMixin
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from misc.models import GenericContentMixin
from collections import defaultdict

User = getattr(settings, "AUTH_USER_MODEL")


class ShiftConfig(TimeStampedModel):
    start = models.TimeField()
    duration = models.IntegerField(default=8)
    number = models.IntegerField(default=3)
    names = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return "{}-{}HRS x {}".format(self.start.strftime('%X'), self.duration, self.number)

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
        stats = defaultdict(int)
        for m in self.mode_set.all().with_shifts():
            stats[m.kind] += m.shifts
        return stats

    def normal_shifts(self):
        data = self.mode_set.filter(kind=Mode.TYPES.N).with_shifts().aggregate(total=Sum('shifts'))
        return data.get('total', 0) or 0

    def __str__(self):
        return "{} [{}]".format(self.description, self.state)


class EventQuerySet(models.QuerySet):
    def active(self, dt=None):
        dt = timezone.now()
        return self.filter(
            (Q(start__isnull=True) | Q(start__lte=dt)) & (Q(end__isnull=True) | Q(end__gte=dt)))

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

    def relevant(self, extras={}):
        yesterday = timezone.now() - timedelta(days=7)
        return self.filter(start__gte=yesterday, start__lte=timezone.now() + timedelta(days=7), **extras)

    def with_duration(self):
        return self.annotate(duration=Hours(F('end'), F('end'), output_field=models.FloatField()))

    def with_hours(self):
        return self.annotate(hours=Hours(F('end'), F('start'), output_field=models.FloatField()))

    def with_shifts(self):
        return self.annotate(shifts=Shifts(F('end'), F('start'), output_field=models.FloatField()))

    def endsbefore(self, event):
        event = event if not isinstance(event, dict) else Struct(**event)
        return self.filter(end__lt=event.start)

    def endsafter(self, event):
        event = event if not isinstance(event, dict) else Struct(**event)
        return self.filter(end__gt=event.end)

    def startsbefore(self, event):
        event = event if not isinstance(event, dict) else Struct(**event)
        return self.filter(start__lt=event.start)

    def startsafter(self, event):
        event = event if not isinstance(event, dict) else Struct(**event)
        return self.filter(start__gt=event.end)

    def within(self, event):
        event = event if not isinstance(event, dict) else Struct(**event)
        return self.filter(start__gte=event.start, end__lte=event.end)

    def matches(self, event):
        event = event if not isinstance(event, dict) else Struct(**event)
        return self.filter(start=event.start, end=event.end)

    def startswith(self, event):
        event = event if not isinstance(event, dict) else Struct(**event)
        return self.filter(start=event.start)

    def endswith(self, event):
        event = event if not isinstance(event, dict) else Struct(**event)
        return self.filter(end=event.end)

    def startswithin(self, event):
        event = event if not isinstance(event, dict) else Struct(**event)
        return self.filter(start__gte=event.start, start__lt=event.end)

    def endswithin(self, event):
        event = event if not isinstance(event, dict) else Struct(**event)
        return self.filter(end__gt=event.start, end__lte=event.end)

    def encloses(self, event):
        event = event if not isinstance(event, dict) else Struct(**event)
        return self.filter(start__lt=event.start, end__gt=event.end)

    def intersects(self, event):
        event = event if not isinstance(event, dict) else Struct(**event)
        return self.filter(
            Q(start__gte=event.start, start__lte=event.end) |
            Q(end__gt=event.start, end__lte=event.end) |
            Q(start__lte=event.start, end__gte=event.end)
        )


class Event(TimeStampedModel, TimeFramedModel):
    cancelled = models.BooleanField(default=False)
    objects = EventQuerySet.as_manager()
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    comments = models.TextField(null=True, blank=True, default="")

    class Meta:
        abstract = True


class ModeTag(TimeStampedModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Mode(Event):
    TYPES = Choices(
        ('N', _('Normal')),
        ('NS', _('Special Beam')),
        ('D', _('Development')),
        ('DS', _('Special Development')),
        ('M', _('Maintenance')),
        ('X', _('Shutdown')),
    )
    kind = models.CharField(_('Type'), choices=TYPES, default=TYPES.N, max_length=10)
    tags = models.ManyToManyField(ModeTag, blank=True)
    objects = EventQuerySet.as_manager()

    def __str__(self):
        return "{0}: {1}-{2}".format(self.kind, self.start, self.end)

    class Meta:
        unique_together = [('schedule', 'start', 'end')]
