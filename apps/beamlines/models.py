import itertools
import re
from functools import lru_cache

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from model_utils import Choices
from model_utils.models import TimeStampedModel

from misc.fields import StringListField
from misc.utils import flatten
from scheduler.models import Event

UserModel = getattr(settings, "AUTH_USER_MODEL")
USO_FACILITY_STAFF_ROLE = getattr(settings, "USO_FACILITY_STAFF_ROLE", "staff:+")
USO_FACILITY_ADMIN_ROLE = getattr(settings, "USO_FACILITY_ADMIN_ROLE", "admin:-")


class FacilityManager(models.Manager):
    def get_by_natural_key(self, acronym):
        return self.get(acronym=acronym)


class Facility(TimeStampedModel):
    STATES = Choices(
        ('design', _('Design')),
        ('construction', _('Construction')),
        ('commissioning', _('Commissioning')),
        ('operating', _('Operating')),
        ('decommissioned', _('Decommissioned')),
    )
    TYPES = Choices(
        ('beamline', _('Beamline')),
        ('sector', _('Sector')),
        ('village', _('Department')),
        ('equipment', _('Equipment')),
    )
    SIZES = Choices(
        (4, 'four', _('Four Hours')),
        (8, 'eight', _('Eight Hours')),
    )
    kind = models.CharField(_('Type'), max_length=50, choices=TYPES, default=TYPES.beamline)
    name = models.CharField(max_length=255, unique=True)
    acronym = models.CharField(max_length=20, unique=True)
    port = models.CharField(max_length=10, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    url = models.URLField(_("Website"), blank=True, null=True)
    range = models.CharField("Spectral Range", max_length=255, null=True, blank=True)
    spot_size = models.CharField("Spot Sizes", max_length=255, null=True, blank=True)
    flux = models.CharField(max_length=255, null=True, blank=True)
    resolution = models.CharField("Spectral Resolution", max_length=255, null=True, blank=True)
    source = models.CharField("Source Type", max_length=255, null=True, blank=True)
    state = models.CharField(max_length=20, choices=STATES, default=STATES.design)
    parent = models.ForeignKey(
        "Facility", null=True, related_name="children", verbose_name="Parent Facility", on_delete=models.SET_NULL
    )
    flex_schedule = models.BooleanField("Allocation Not Required", default=False)
    shift_size = models.IntegerField("Shift Size (hrs)", choices=SIZES, default=SIZES.eight)
    details = models.JSONField(default=dict, blank=True, editable=False)

    objects = FacilityManager()

    def __str__(self):
        return self.acronym

    def active_config(self):
        return self.configs.filter(cycle__start_date__lte=timezone.now().date()).latest('cycle')

    def active_techniques(self):
        from proposals import models
        tree = self.dtrace()
        item_ids = models.FacilityConfig.objects.filter(facility__in=tree).active().values_list('items', flat=True)
        return models.ConfigItem.objects.filter(pk__in=item_ids)

    def tags(self):
        return FacilityTag.objects.filter(
            Q(facility=self) | Q(facility__children=self) | Q(facility__parent=self)
        ).distinct()

    def utrace(self, stop=None):
        if self.parent and self.parent.kind != stop:
            return [self] + self.parent.utrace()
        else:
            return [self]

    def dtrace(self, stop=None):
        tree = itertools.chain(child.dtrace(stop=stop) for child in self.children.all())
        return [self] + flatten(*tree)

    def is_user(self, user, remote=False):
        perms = {
            True: ['{}-REMOTE-USER', '{}-USER'],
            False: ['{}-USER']
        }[remote]
        _perms = [perm.format(bl.acronym) for bl in self.utrace(stop='village') for perm in perms]
        return user.has_any_perm(*_perms) or self.is_staff(user)

    @lru_cache(maxsize=128)
    def expand_role(self, full_role: str) -> list[str]:
        """
        Takes a role string of the form <role>(:[+-*])? expands it for this facility and it's parents
        or children.
        :param full_role: The role string to expand
        """

        if m := re.match(r'^(?P<role>[\w_-]+)(?::(?P<wildcard>[+*-]))?$', full_role):
            role = m.group('role')
            wildcard = m.group('wildcard')
            if wildcard == '+':
                return [f"{role}:{bl.acronym.lower()}" for bl in self.dtrace()]
            elif wildcard == '-':
                return [f"{role}:{bl.acronym.lower()}" for bl in self.utrace()]
            elif wildcard == '*':
                return [f"{role}:{self.acronym.lower()}"]
            else:
                return [full_role.format(self.acronym.lower())]

        return [full_role.format(self.acronym.lower())]

    def is_staff(self, user):
        _roles = self.expand_role(USO_FACILITY_STAFF_ROLE)
        return user.has_any_role(*_roles)

    def is_admin(self, user):

        _roles = self.expand_role(USO_FACILITY_ADMIN_ROLE)
        return user.has_any_role(*_roles)

    def staff_list(self):
        User = get_user_model()
        return User.objects.all_with_roles(*self.expand_role(USO_FACILITY_STAFF_ROLE))

    def natural_key(self):
        return (self.acronym,)

    class Meta:
        verbose_name_plural = _("Facilities")


class UserSupport(Event):
    staff = models.ForeignKey(UserModel, related_name="support", on_delete=models.CASCADE)
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="support")
    tags = models.ManyToManyField('beamlines.FacilityTag', related_name='support', blank=True)

    def __str__(self):
        return "{}/{} {}-{}".format(
            self.staff.username, self.facility.acronym, self.start.isoformat(),
            self.end.isoformat()
        )

    class Meta:
        unique_together = [('staff', 'facility', 'start')]


class FacilityTag(TimeStampedModel):
    CATEGORIES = Choices(
        ('scheduling', _('Scheduling')),
        ('priority', _('Priority Area')),
        ('other', _('Other')),
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=200, blank=True, null=True)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Lab(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    acronym = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    admin_roles = StringListField(null=True, blank=True)
    permissions = models.ManyToManyField("samples.SafetyPermission", blank=True)
    details = models.JSONField(default=dict, blank=True, editable=False)
    available = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def permission_names(self):
        return ', '.join(self.permissions.values_list('code', flat=True))

    permission_names.short_description = 'Permissions'
    permission_names.sort_field = 'permissions__code'

    def num_workspaces(self):
        return self.workspaces.count()

    num_workspaces.short_description = 'Workspaces'


class LabWorkSpace(TimeStampedModel):
    lab = models.ForeignKey(Lab, related_name='workspaces', on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    available = models.BooleanField(default=True)

    def __str__(self):
        return '{}/{}'.format(self.name, self.description)

    def sessions(self):
        return self.lab.lab_sessions.filter(workspaces=self).distinct()

    class Meta:
        unique_together = [('lab', 'name')]


class Ancillary(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    admin_roles = StringListField(null=True, blank=True)
    permissions = models.ManyToManyField("samples.SafetyPermission", blank=True)
    details = models.JSONField(default=dict, blank=True, editable=False)
    available = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Ancillaries'
