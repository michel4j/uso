import uuid
from django.db import models
from django.conf import settings
from model_utils.models import TimeStampedModel
from misc.models import DateSpanMixin, DateSpanQuerySet
from misc.fields import StringListField
from model_utils import Choices
from django.utils.translation import ugettext as _

User = getattr(settings, "AUTH_USER_MODEL")


class AgreementQuerySet(DateSpanQuerySet):
    def required_for_user(self, user):
        query = models.Q()
        for role in user.get_all_roles():
            query |= models.Q(roles__icontains=role)
        return self.filter(query, state=Agreement.STATES.enabled)

    def active_for_user(self, user):
        return self.filter(users__pk=user.pk, acceptances__active=True)

    def pending_for_user(self, user):
        return self.required_for_user(user).exclude(pk__in=self.active_for_user(user).values_list('pk', flat=True)).distinct()


class AgreementManager(models.Manager.from_queryset(AgreementQuerySet)):
    use_for_releated_fields = True


class Agreement(DateSpanMixin, TimeStampedModel):
    STATES = Choices(
        ("disabled", _("Disabled")),
        ("enabled", _("Enabled")),
        ("archived", _("Archived")),
    )
    code = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    state = models.CharField(max_length=10, choices=STATES, default=STATES.disabled)
    description = models.TextField("Short Description", blank=True)
    content = models.TextField("Agreement Text", blank=True)
    roles = StringListField("Required for users with these roles", blank=True, help_text="Separate entries with semi-colons")
    users = models.ManyToManyField(User, through="Acceptance", related_name="agreements")

    objects = AgreementManager()

    def __unicode__(self):
        return self.name + "" if self.state == self.STATES.enabled else "{}".format(self.get_state_display())

    def num_users(self):
        return self.acceptances.filter(active=True).count()

    def valid_for_user(self, user):
        return self.acceptances.filter(active=True).filter(user=user).exists()


class Acceptance(TimeStampedModel):
    agreement = models.ForeignKey(Agreement, related_name='acceptances')
    user = models.ForeignKey(User, related_name="acceptances")
    host = models.GenericIPAddressField(blank=True, null=True)
    active = models.BooleanField(default=True)

    def __unicode__(self):
        return "{}-{}".format(self.agreement, self.user)