from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from model_utils import Choices
from model_utils.models import TimeStampedModel

NOTIFIER_DEBUG = getattr(settings, 'NOTIFIER_DEBUG', True)
NOTIFIER_FILTER = getattr(settings, 'NOTIFIER_FILTER', None)


class NotificationQueryset(models.QuerySet):
    def prioritize(self):
        return self.order_by('-created', '-level', 'state')

    def web(self):
        return self.exclude(kind=MessageTemplate.TYPES.email)

    def email(self):
        return self.exclude(kind=MessageTemplate.TYPES.web)

    def urgent(self):
        return self.filter(level__gte=Notification.LEVELS.urgent).exclude(state=Notification.STATES.acknowledged)

    def info(self):
        return self.filter(level=Notification.LEVELS.info) | self.filter(level__gte=1, state__gte=2)

    def important(self):
        return self.filter(level__gte=Notification.LEVELS.important).exclude(state=Notification.STATES.acknowledged)

    def pending(self):
        return self.exclude(state=Notification.STATES.acknowledged).exclude(level__lte=1, state__gte=2)

    def relevant(self):
        one_week = timezone.now() - timedelta(days=7)
        yesterday = timezone.now() - timedelta(days=1)
        return self.filter(
            Q(state=1) |
            Q(level=0, state__gt=1, modified__gte=yesterday) |
            Q(level__gt=0, state__gt=1, modified__gte=one_week)
        )


class Notification(TimeStampedModel):
    STATES = Choices(
        (0, 'queued', _('Queued')),
        (1, 'sent', _('Sent')),
        (2, 'read', _('Read')),
        (3, 'acknowledged', _('Acknowledged')),
        (4, 'failed', _('Failed'))
    )
    LEVELS = Choices(
        (0, 'info', _('Information')),  # non-urgent information
        (1, 'important', _('Important')),  # important, acknowledgement required
        (2, 'urgent', _('Urgent')),  # very important, acknowledgement required
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, related_name='notifications',
        on_delete=models.SET_NULL
    )
    emails = models.JSONField(blank=True, default=list)
    kind = models.CharField("Type", max_length=100)
    level = models.PositiveSmallIntegerField(choices=LEVELS, default=LEVELS.info)
    send_on = models.DateTimeField(null=True)
    state = models.PositiveSmallIntegerField(choices=STATES, default=STATES.queued)
    data = models.TextField("Message", blank=True)
    objects = NotificationQueryset.as_manager()

    def note_type(self):
        return MessageTemplate.objects.get(name=self.kind)

    def to(self):
        return self.user if self.user else ', '.join(self.emails)

    def title(self):
        return self.note_type().description

    def is_active(self):
        return (self.level, self.state) not in [(0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]

    def deliver(self):
        note_type = self.note_type()
        if self.state == self.STATES.queued and note_type.kind in [MessageTemplate.TYPES.email,
                                                                   MessageTemplate.TYPES.full]:
            if self.user:
                recipients = [self.user.email]
            elif self.emails:
                recipients = self.emails
            else:
                return
            original_recipients = recipients
            if NOTIFIER_FILTER:
                recipients = list(filter(NOTIFIER_FILTER, recipients))

            if settings.DEBUG or NOTIFIER_DEBUG:
                message = "{}\n--------------\n DEBUG: INTENDED RECIPIENTS [{}]".format(
                    self.data, ', '.join(original_recipients)
                )
                recipients = [u[1] for u in settings.ADMINS]
            else:
                message = self.data
            subject = "{} {}".format(settings.EMAIL_SUBJECT_PREFIX, note_type.description)
            success = send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True)
            self.state = self.STATES.sent if success else self.STATES.failed
        else:
            self.state = self.STATES.sent
        self.save()

    def __str__(self):
        note_type = self.note_type()
        subject = note_type.description
        return "{}: {}".format(subject, self.user if self.user else "; ".join(self.emails))


class MessageTemplateQueryset(models.QuerySet):
    def active(self):
        return self.filter(active=True)

    def latest_for(self, name):
        return self.filter(name=name, active=True).order_by('-modified').first()


class MessageTemplate(TimeStampedModel):
    TYPES = Choices(
        ('full', 'Web and Email notification'),
        ('web', 'Web notification'),
        ('email', 'Email notification'),
    )
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=100, blank=True)
    kind = models.CharField(max_length=10, choices=TYPES, default=TYPES.full)
    content = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    objects = MessageTemplateQueryset.as_manager()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Message Template"
        verbose_name_plural = "Message Templates"
