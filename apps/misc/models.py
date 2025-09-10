import hashlib
import os
import uuid
from mimetypes import MimeTypes

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q, F, Count, Min, Max, Value
from django.db.models.functions import Coalesce
from django.db.models.query import QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _
from model_utils.choices import Choices
from model_utils.models import TimeStampedModel

from .fields import RestrictedFileField
from .utils import get_code_generator, get_client_address

User = getattr(settings, "AUTH_USER_MODEL")


class DateSpanQuerySet(QuerySet):
    """Add queryset methods for filtering currently active entries based on 'start_date'
    and 'end_date' fields
    """

    def active(self, dt=None):
        """Return the queryset representing all objects with no end_date or
        with end_dates after the specified date, or today if no date is specified"""
        dt = timezone.now().date() if not dt else dt
        return self.filter(
            (Q(start_date__isnull=True) | Q(start_date__lte=dt)) & (Q(end_date__isnull=True) | Q(end_date__gte=dt))
        )

    def expired(self, dt=None):
        """Return the queryset representing all objects with an end_date prior
        to current date"""
        dt = timezone.now().date() if not dt else dt
        return self.filter(Q(end_date__isnull=False) & Q(end_date__lt=dt))

    def pending(self, dt=None):
        """Return the queryset representing all objects with an start_date in the future"""
        dt = timezone.now().date() if not dt else dt
        return self.filter(Q(start_date__gt=dt))

    def next(self, dt=None):
        """Return the next instance by start_date"""
        dt = timezone.now().date() if not dt else dt
        return self.filter(start_date__gt=dt).order_by('start_date').first()

    def prev(self, dt=None):
        """Return the next instance by start_date"""
        dt = timezone.now().date() if not dt else dt
        return self.filter(start_date__lt=dt).order_by('-start_date').first()

    def inactive(self):
        """A proxy for expired"""
        return self.expired()

    def former(self):
        """A proxy for expired"""
        return self.expired()

    def current(self):
        """A proxy for current"""
        return self.active()

    def count_by_year(self, **kwargs):
        """Aggregate the object counts by year. returns a list of dictionaries
        such as [{'year': '2007', 'my_var': 127}, ..., ].  Kwargs map the search field
        name to the count attribute name. For example, count_by_year(start_date='joined')
        returns a list such as [{'year': '2007', 'joined': 135}, {'year': '2008', 'joined': 105}]
        which represents the aggregated count of every object in the table with the start_date
        field corresponding to those years.

        Only one kwarg is supported at the moment. The method is final, no queryset methods
        can be called on the result.
        """

        ann_kw = {v: Count('id', distinct=True) for v in list(kwargs.values())}
        ext_kw = {'year': settings.DB_DATE_FUNCS['year'].format(k) for k, v in list(kwargs.items())}
        return self.extra(ext_kw).values('year').annotate(**ann_kw)


class DateSpanManager(models.Manager.from_queryset(DateSpanQuerySet)):
    use_for_related_fields = True


class DateSpanMixin(models.Model):
    """
    A mixin class that adds the fields, methods and managers necessary to support
    date-spanning.
    """
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    objects = DateSpanManager()

    def is_active(self, dt=None):
        dt = timezone.localtime(timezone.now()).date() if not dt else dt
        return (self.start_date is None or self.start_date <= dt) and (self.end_date is None or self.end_date >= dt)

    def is_pending(self, dt=None):
        dt = timezone.localtime(timezone.now()).date() if not dt else dt
        return self.start_date is not None and self.start_date > dt

    def is_expired(self, dt=None):
        dt = timezone.localtime(timezone.now()).date() if not dt else dt
        return self.end_date is not None and self.end_date < dt

    class Meta:
        abstract = True


class GenericContentQueryset(QuerySet):
    def get_by_natural_key(self, content_type, object_id):
        return self.get(content_type=content_type, object_id=object_id)


class GenericContentManager(models.Manager.from_queryset(GenericContentQueryset)):
    use_for_related_fields = True


class GenericContentMixin(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    reference = GenericForeignKey('content_type', 'object_id')
    objects = GenericContentManager()

    class Meta:
        abstract = True

    def natural_key(self):
        return self.content_type, self.object_id


class ClarificationQuerySet(QuerySet):
    def pending(self):
        return self.filter(response__isnull=True)

    def completed(self):
        return self.exclude(response__isnull=True)


class ClarificationManager(models.Manager.from_queryset(ClarificationQuerySet)):
    use_for_related_fields = True

    def get_by_natural_key(self, content_type, object_id):
        return self.get(content_type=content_type, object_id=object_id)


class Clarification(GenericContentMixin, TimeStampedModel):
    requester = models.ForeignKey(User, related_name='questions', on_delete=models.CASCADE)
    responder = models.ForeignKey(User, related_name='responses', null=True, on_delete=models.SET_NULL)
    question = models.TextField()
    response = models.TextField(blank=True, null=True)
    objects = ClarificationManager()

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"{self.requester.get_full_name()}[{self.pk}]: {self.reference}"


def attachment_file(instance, filename):
    ext = os.path.splitext(filename)[-1]
    return os.path.join('attachments', instance.content_type.model, str(instance.object_id), instance.slug + ext)


class AttachmentQuerySet(QuerySet):

    def scientific(self):
        return self.filter(kind=Attachment.TYPES.scientific)

    def safety(self):
        return self.filter(kind=Attachment.TYPES.safety)

    def ethics(self):
        return self.filter(kind=Attachment.TYPES.ethics)

    def other(self):
        return self.filter(kind=Attachment.TYPES.other)


class AttachmentManager(models.Manager.from_queryset(AttachmentQuerySet)):
    use_for_related_fields = True


class Attachment(GenericContentMixin, TimeStampedModel):
    TYPES = Choices(
        ('scientific', _('Scientific')),
        ('safety', _('Safety')),
        ('ethics', _('Ethics')),
        ('other', _('Other')),
    )
    owner = models.ForeignKey(User, related_name='attachments', on_delete=models.CASCADE)
    description = models.CharField(max_length=100, verbose_name="Description")
    file = RestrictedFileField(
        upload_to=attachment_file, max_size=2097152,
        file_types=['application/pdf', 'image/png', 'image/jpeg', 'image/webp'], verbose_name="Attachment"
    )
    slug = models.SlugField(max_length=50, blank=True, unique=True)
    kind = models.CharField(choices=TYPES, max_length=20, verbose_name="Type")
    is_editable = models.BooleanField(default=True)

    objects = AttachmentManager()

    def save(self, *args, **kwargs):
        h = hashlib.md5(
            f"{self.file.name}{self.content_type}{self.object_id}{self.owner.pk}{timezone.now().isoformat()}".encode(
                'utf-8'
            )
        )
        self.slug = h.hexdigest()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not Attachment.objects.exclude(pk=self.pk).filter(file=self.file).exists():
            self.file.delete(False)
        super().delete(*args, **kwargs)

    def mime_type(self):
        mime = MimeTypes()
        return mime.guess_type(self.file.path)[0]

    def is_image(self):
        mime_type = self.mime_type()
        if mime_type:
            return 'image' in mime_type
        return False

    def exists(self):
        return self.file.storage.exists(self.file.path)

    def __str__(self):
        filename = os.path.basename(self.file.name)
        return f"{filename} [{self.get_kind_display()}]"


class ActivityLogQueryset(QuerySet):
    def get_by_natural_key(self, content_type, object_id):
        return self.get(content_type=content_type, object_id=object_id)

    def filter_by(self, model=None, obj=None):
        if model:
            content_type = ContentType.objects.get_for_model(model)
            return self.filter(content_type=content_type)
        elif obj:
            content_type = ContentType.objects.get_for_model(obj)
            return self.filter(content_type=content_type, object_id=obj.pk)
        else:
            return self


class ActivityLogManager(models.Manager.from_queryset(ActivityLogQueryset)):
    use_for_related_fields = True

    def log(self, request, obj, kind, description=''):
        info = {
            'user': request.user,
            'user_name': request.user.get_full_name(),
            'address': get_client_address(request),
            'kind': kind,
            'description': description,
            'reference': obj,
        }
        self.create(**info)


class ActivityLog(GenericContentMixin, TimeStampedModel):
    TYPES = Choices(
        ('task', _('Task Performed')),
        ('create', _('Created')),
        ('modify', _('Modified')),
        ('delete', _('Deleted')),
    )
    user = models.ForeignKey(User, related_name="activities", null=True, blank=True, on_delete=models.SET_NULL)
    user_name = models.CharField('User name', max_length=60)
    address = models.GenericIPAddressField('IP Address')
    kind = models.CharField(choices=TYPES, max_length=20, verbose_name="Type")
    description = models.TextField(blank=True)

    objects = ActivityLogManager()

    class Meta:
        ordering = ('-created',)

    def __str__(self):
        return f'{self.get_kind_display()},{self.content_type}[{self.object_id}]/{self.created.isoformat()}'


class CodeModelMixin(models.Model):
    """
    A mixin class that adds the fields, methods and managers necessary to support
    code models.
    """
    code = models.SlugField(unique=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Override save method to clear code if pk is None
        """
        new_code_needed = (self.pk is None)  # when cloning, for example
        if new_code_needed:
            self.code = uuid.uuid4()

        super().save(*args, **kwargs)
        if new_code_needed:
            key = self.__class__.__name__.upper()
            code_func = get_code_generator(key)
            self.code = code_func(self)
            self.save(update_fields=['code'])

    def __str__(self):
        return f"{self.code}"

    def natural_key(self):
        return self.code,

    def year_index(self) -> int:
        """
        Returns the index of this instance within it's creation year. That is, the index of the instance
        when sorted by creation date within the year it was created.
        """
        index = self.__class__.objects.filter(
            created__year=self.created.year, pk__lte=self.pk
        ).aggregate(
            count=Value(1) + Coalesce(Max('pk') - Min('pk'), 0)
        )['count'] or 1
        return index

    def month_index(self) -> int:
        """
        Returns the index of this instance within it's creation month. That is, the index of the instance
        when sorted by creation month within the month it was created.
        """
        index = self.__class__.objects.filter(
            created__year=self.created.year, created__month=self.created.month,
            pk__lte=self.pk
        ).aggregate(
            count=Value(1) + Coalesce(Max('pk') - Min('pk'), 0)
        )['count'] or 1
        return index
