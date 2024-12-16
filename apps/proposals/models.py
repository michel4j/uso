import os
from collections import OrderedDict
from datetime import date, timedelta

import numpy
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models import Case, Avg, When, F, Q, StdDev, Max
from django.db.models.query import QuerySet
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from model_utils import Choices
from model_utils.models import TimeStampedModel

from beamlines.models import Facility
from dynforms.models import DynEntryMixin, FormType
from misc.fields import StringListField
from misc.models import DateSpanMixin, DateSpanQuerySet, Attachment, Clarification, GenericContentMixin, \
    GenericContentQueryset
from publications.models import SubjectArea


User = getattr(settings, "AUTH_USER_MODEL")
USO_SAFETY_REVIEWS = getattr(settings, "USO_SAFETY_REVIEWS", [])
USO_TECHNICAL_REVIEWS = getattr(settings, "USO_TECHNICAL_REVIEWS", [])
USO_SCIENCE_REVIEWS = getattr(settings, "USO_SCIENCE_REVIEWS", [])
USO_SAFETY_APPROVAL = getattr(settings, "USO_SAFETY_APPROVAL", 'approval')


def _proposal_filename(instance, filename):
    ext = os.path.splitext(filename)[-1]
    return os.path.join('proposals', str(instance.proposal.pk), instance.slug + ext)


class Proposal(DynEntryMixin):
    STATES = Choices(
        (0, 'draft', 'Not Submitted'),
        (1, 'submitted', 'Submitted')
    )
    spokesperson = models.ForeignKey(User, related_name='+', on_delete=models.CASCADE)
    leader_username = models.CharField(max_length=50, null=True, blank=True)
    delegate_username = models.CharField(max_length=50, null=True, blank=True)
    title = models.TextField(null=True)
    keywords = models.TextField(null=True)
    areas = models.ManyToManyField(
        SubjectArea, verbose_name="Research Subject Areas", blank=True, related_name='proposals'
    )
    team = StringListField(blank=True, null=True)
    state = models.IntegerField(choices=STATES, default=STATES.draft)
    clarifications = GenericRelation(Clarification)
    attachments = GenericRelation(Attachment)

    @property
    def code(self):
        return '{0:0>6}'.format(
            self.pk, )

    def is_editable(self):
        return self.state == self.STATES.draft

    def authors(self):
        return " \u00b7 ".join(["{last_name}, {first_name}".format(**member) for member in self.get_full_team()])

    def __str__(self):
        title = self.title if self.title else 'No title'
        short_title = title if len(title) <= 52 else title[:52] + '..'
        return "{} - {}".format(self.pk, short_title)

    def get_absolute_url(self):
        reverse('proposal-detail', kwargs={'pk': self.pk})

    def get_full_team(self):
        """Return a unique list of team members including everyone with team roles ('leader', 'delegate' and
        'spokesperson'). The team roles for each member will be in the key 'roles' which is a list """

        full_team = OrderedDict()
        full_team[self.spokesperson.email.strip().lower()] = {
            'first_name': self.spokesperson.first_name, 'last_name': self.spokesperson.last_name,
            'email': self.spokesperson.email.strip().lower(),
            'roles': ['spokesperson']
        }
        leader = self.details.get('leader', {})
        for k in ['delegate', '*', 'leader']:
            if k == '*':
                for member in self.details.get('team_members', []):
                    email = member.get('email', '').strip().lower()
                    if email in full_team: continue
                    if email == leader.get("email", '').strip().lower(): continue
                    full_team[email] = {
                        'first_name': member.get('first_name', ''), 'last_name': member.get('last_name', ''),
                        'email': email, 'roles': []
                    }
            else:
                member = self.details.get(k, {})
                if member and member.get('email', '').strip():
                    email = member['email'].strip().lower()
                    if email in full_team:
                        full_team[email]['roles'].append(k)
                    else:
                        full_team[email] = {
                            'first_name': member.get('first_name', ''), 'last_name': member.get('last_name', ''),
                            'email': email, 'roles': [k]
                        }

        return list(full_team.values())

    def get_delegate(self):
        return get_user_model().objects.filter(username=self.delegate_username).first()

    def get_leader(self):
        return get_user_model().objects.filter(username=self.leader_username).first()

    def get_member(self, info):
        email = info['email'].strip()
        if email:
            return get_user_model().objects.filter(
                models.Q(email__iexact=email) | models.Q(alt_email__iexact=email)
            ).first()

    def get_techniques(self):
        techs = [int(v) for v in self.details['beamline_reqs'][0]['techniques']]

        # filter to only techniques available in database
        self.details['beamline_reqs'][0]['techniques'] = list(
            Technique.objects.filter(pk__in=techs).values_list('pk', flat=True)
        )
        Proposal.objects.filter(pk=self.pk).update(details=self.details)


class SubmissionQuerySet(QuerySet):

    def with_scores(self):
        """
        Calculate average and standard deviations of each review type
        :return:
        """
        annotations = {}
        for rev_type in ReviewType.objects.scored():

            annotations[f"{rev_type.code}_avg"] = Avg(
                Case(
                    When(Q(reviews__is_complete=True, reviews__type=rev_type), then=F('reviews__score')),
                    output_field=models.FloatField()
                )
            )
            annotations[f"{rev_type.code}_std"] = StdDev(
                Case(
                    When(Q(reviews__is_complete=True, reviews__type=rev_type), then=F('reviews__score')),
                    output_field=models.FloatField()
                )
            )
        return self.annotate(**annotations).distinct()


class SubmissionManager(models.Manager.from_queryset(SubmissionQuerySet)):
    use_for_related_fields = True


from django.db.models.functions import Concat
from misc.functions import String, LPad

_submission_code_func = Concat(
    'track__acronym', LPad(
        String('proposal_id'), 6
    ), output_field=models.CharField()
)


class Submission(TimeStampedModel):
    STATES = Choices(
        (0, 'pending', 'Pending'), (1, 'started', 'Started'), (2, 'reviewed', 'Reviewed'),
        (3, 'complete', 'Complete'), )
    TYPES = Choices(
        ('user', 'User Access'), ('staff', 'Staff Access'), ('purchased', 'Purchased Access'),
        ('beamteam', 'Beam Team'),
        ('education', 'Education/Outreach')
    )
    proposal = models.ForeignKey(Proposal, related_name='submissions', on_delete=models.CASCADE)
    kind = models.CharField(_('Access Type'), max_length=20, choices=TYPES, default=TYPES.user)
    track = models.ForeignKey('ReviewTrack', on_delete=models.CASCADE, related_name='submissions')
    cycle = models.ForeignKey("ReviewCycle", on_delete=models.CASCADE, related_name='submissions')
    state = models.IntegerField(choices=STATES, default=STATES.pending)
    techniques = models.ManyToManyField('ConfigItem', blank=True, related_name='submissions')
    reviews = GenericRelation('proposals.Review')
    comments = models.TextField(blank=True)
    objects = SubmissionManager()

    @property
    def code(self):
        return f'{self.track.acronym}{self.proposal.pk:0>6}'

    def reviewer(self):
        return get_user_model().objects.filter(
            pk__in=self.reviews.filter(reviewer__reviewer__committee=self.track).values_list('reviewer', flat=True)
        ).order_by('?').first()

    def __str__(self):
        return '{}~{}'.format(
            self.code, self.proposal.spokesperson.last_name, )

    def get_absolute_url(self):
        return reverse('submission-detail', kwargs={'pk': self.pk})

    def title(self):
        return self.proposal.title

    def siblings(self):
        return self.proposal.submissions.exclude(pk=self.pk)

    def facilities(self):
        return Facility.objects.filter(pk__in=self.techniques.values_list('config__facility', flat=True)).distinct()

    facilities.sort_field = 'techniques__config__facility__acronym'

    def close(self):
        comments = ""
        for n, review in enumerate(self.reviews.complete()):
            text = review.details.get('comments', '').strip()
            if not text: continue
            comments += f"**Reviewer #**{n + 1} ({review.type}): {text}  \n\n"
        self.comments = comments
        Submission.objects.filter(pk=self.pk).update(
            comments=comments, state=self.STATES.reviewed, modified=timezone.localtime(timezone.now())
        )

    def scores(self):
        summary = self.reviews.score_summary()
        summary['facilities'] = {
            int(r.details.get('requirements', {}).get('facility', 0)): r.score
            for r in self.reviews.technical().complete()
        }
        return summary

    def adj(self):
        if hasattr(self, 'adjustment'):
            adj = self.adjustment.value
        else:
            adj = 0
        return adj

    def score(self):
        if hasattr(self, 'adjustment'):
            adj = self.adjustment.value
        else:
            adj = 0

        if hasattr(self, 'merit') and self.merit:
            return self.merit + adj
        else:
            scores = self.scores()
            score = scores.get('merit', 0.0) + adj
            score = score if score else 0.0
        return score

    class Meta:
        unique_together = ("proposal", "track")


class ScoreAdjustment(TimeStampedModel):
    submission = models.OneToOneField(Submission, related_name='adjustment', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.TextField()
    value = models.FloatField(default=0.5)

    def __str__(self):
        return '{} Score Adjustment: {:+}'.format(self.submission, self.value)


class ReviewTrack(TimeStampedModel):
    name = models.CharField(max_length=128)
    acronym = models.CharField(max_length=10, unique=True)
    description = models.TextField(null=True)
    special = models.BooleanField("Special Requests", null=True, default=None, unique=True)
    min_reviewers = models.IntegerField("Min Reviews/Proposal", default=0)
    max_proposals = models.IntegerField("Max Proposals/Reviewer", default=0)
    notify_offset = models.IntegerField("Notification Delay (days)", default=1)

    def __str__(self):
        return "{0} - {1}".format(self.acronym, self.name)


class ReviewCycleQuerySet(DateSpanQuerySet):

    def archived(self):
        return self.filter(state=ReviewCycle.STATES.archive)

    def pending(self, dt=None):
        """Return the queryset representing all objects with an start_date in the future"""
        dt = timezone.now().date() if not dt else dt
        return self.filter(Q(open_date__gt=dt))

    def open(self):
        return self.filter(state=ReviewCycle.STATES.open)

    def next_call(self, dt=None):
        dt = timezone.now().date() if not dt else dt
        return self.filter(open_date__gte=dt).first()

    def review(self):
        return self.filter(state=ReviewCycle.STATES.review)

    def evaluation(self):
        return self.filter(state=ReviewCycle.STATES.evaluation)

    def schedule(self):
        return self.filter(state=ReviewCycle.STATES.schedule)


class ReviewCycleManager(models.Manager.from_queryset(ReviewCycleQuerySet)):
    use_for_related_fields = True


class ReviewCycle(DateSpanMixin, TimeStampedModel):
    STATES = Choices(
        (0, 'pending', _('Call Pending')), (1, 'open', _('Call Open')), (2, 'assign', _('Assigning')),
        (3, 'review', _('Review')),
        (4, 'evaluation', _('Allocation')), (5, 'schedule', _('Scheduling')), (6, 'active', _('Active')),
        (7, 'archive', _('Archived')), )
    TYPES = Choices(
        ('mock', 'Mock Cycle'), ('normal', 'Normal Cycle'), )
    kind = models.CharField(_('Cycle Type'), max_length=20, choices=TYPES, default=TYPES.normal)
    open_date = models.DateField(_("Call Open Date"))
    close_date = models.DateField(_("Call Close Date"))
    alloc_date = models.DateField(_("Allocation Date"))
    due_date = models.DateField(_("Reviews Due"), null=True)
    reviewers = models.ManyToManyField("Reviewer", blank=True, related_name='cycles')
    state = models.SmallIntegerField(default=0, choices=STATES)
    schedule = models.OneToOneField("scheduler.Schedule", related_name='cycle', on_delete=models.CASCADE)
    objects = ReviewCycleManager()

    def live_schedule(self):
        return self.schedule

    def configs(self):
        return FacilityConfig.objects.active(cycle=self.pk)

    def techniques(self):
        return Technique.objects.filter(pk__in=self.configs().values_list('techniques', flat=True)).distinct()

    def tracks(self):
        return ReviewTrack.objects.filter(pk__in=self.submissions.values_list('track', flat=True))

    def num_submissions(self):
        return self.submissions.count()

    num_submissions.short_description = 'Proposals'

    def num_facilities(self):
        return self.configs().count()

    num_facilities.short_citation = 'Facilities'

    def is_closed(self):
        return self.close_date < timezone.now().date()

    def is_open(self):
        return self.state == self.STATES.open

    def last_date(self):
        return self.end_date - timedelta(days=1)

    def name(self):
        return "{}-{} {}".format(
            self.start_date.strftime('%b'), self.last_date().strftime('%b'), self.start_date.strftime('%Y')
        )

    def __str__(self):
        return self.name()

    class Meta:
        unique_together = ("start_date", "open_date")
        get_latest_by = "start_date"


class Technique(TimeStampedModel):
    TYPES = Choices(
        ('diffraction', _('Diffraction/Scattering')), ('imaging', _('Imaging/Microscopy')),
        ('spectroscopy', _('Spectroscopy')),
        ('other', _('Other')), )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(_('Category'), max_length=50, choices=TYPES, default=TYPES.other)
    acronym = models.CharField(_('Acronym'), max_length=20, null=True, blank=True)

    def __str__(self):
        return self.name if not self.acronym else '{} ({})'.format(self.name, self.acronym)

    def short_name(self):
        return self.name if not self.acronym else self.acronym

    class Meta:
        ordering = ['category']


class FacilityConfigQueryset(models.QuerySet):
    def active(self, cycle=None, year=None, d=None):
        pre_extras = {}
        extras = {'cycle': F('latest')}
        if cycle:
            pre_extras['facility__configs__cycle__lte'] = cycle

        if year and not d:
            d = date(year, 12, 31)
        elif not cycle and not year:
            d = timezone.now().date()

        if d:
            pre_extras['facility__configs__cycle__start_date__lte'] = d

        return self.annotate(
            latest=Max(
                Case(
                    When(Q(**pre_extras), then=F('facility__configs__cycle')), output_field=models.IntegerField()
                )
            )
        ).filter(**extras)

    def accepting(self):
        return self.filter(accept=True)

    def pending(self, d=None):
        if not d:
            d = timezone.now().date()
        return self.filter(cycle__start_date__gt=d)

    def expired(self, cycle=None, year=None, d=None):
        pre_extras = {}
        extras = {'cycle__lt': F('latest')}
        if cycle:
            pre_extras['facility__configs__cycle__lte'] = cycle

        if year and not d:
            d = date(year, 12, 31)
        elif not cycle and not year:
            d = timezone.now().date()

        if d:
            pre_extras['facility__configs__cycle__start_date__lte'] = d

        return self.annotate(
            latest=Max(
                Case(
                    When(Q(**pre_extras), then=F('facility__configs__cycle')), output_field=models.IntegerField()
                )
            )
        ).filter(**extras)


class FacilityConfigManager(models.Manager.from_queryset(FacilityConfigQueryset)):
    use_for_related_fields = True


class FacilityConfig(TimeStampedModel):
    cycle = models.ForeignKey(ReviewCycle, verbose_name=_('Start Cycle'), on_delete=models.CASCADE)
    accept = models.BooleanField("Accept Proposals", default=False)
    facility = models.ForeignKey(Facility, related_name="configs", on_delete=models.CASCADE)
    techniques = models.ManyToManyField(Technique, through="ConfigItem", related_name="configs")
    comments = models.TextField(blank=True, null=True)
    objects = FacilityConfigManager()

    class Meta:
        unique_together = ("cycle", "facility")
        get_latest_by = "cycle"
        ordering = ['-cycle']
        verbose_name = "Facility Configuration"

    def __str__(self):
        if self.pk:
            return "{}/{}".format(self.facility.acronym, self.cycle.pk)
        else:
            return "<unsaved>"

    def is_active(self):
        return FacilityConfig.objects.filter(facility=self.facility, pk=self.pk).active().exists()

    def is_editable(self):
        return self.cycle.open_date > timezone.now().date()

    def siblings(self):
        return FacilityConfig.objects.filter(facility=self.facility).exclude(pk=self.pk)


class ConfigItemQueryset(models.QuerySet):
    def operating(self):
        return self.filter(state=ConfigItem.STATES.operating)

    def commissioning(self):
        return self.filter(state=ConfigItem.STATES.commissioning)

    def group_by_track(self):
        return {track: self.filter(track=track) for track in ReviewTrack.objects.all()}


class ConfigItemManager(models.Manager.from_queryset(ConfigItemQueryset)):
    use_for_related_fields = True


class ConfigItem(TimeStampedModel):
    STATES = Choices(
        ('design', 'Design'), ('construction', 'Construction'), ('commissioning', 'Commissioning'),
        ('operating', 'Active'), )
    config = models.ForeignKey(FacilityConfig, related_name="items", on_delete=models.CASCADE)
    technique = models.ForeignKey(Technique, related_name="items", on_delete=models.CASCADE)
    state = models.CharField(choices=STATES, default=STATES.operating, max_length=30)
    track = models.ForeignKey("ReviewTrack", on_delete=models.CASCADE)
    objects = ConfigItemManager()

    class Meta:
        unique_together = [("config", "technique")]

    def __str__(self):
        return "{}/{}/{}".format(self.config, self.track.acronym, self.technique.short_name())


class Reviewer(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    techniques = models.ManyToManyField(Technique, related_name="reviewers")
    areas = models.ManyToManyField(SubjectArea, verbose_name=_('Subject Areas'), )
    karma = models.DecimalField(max_digits=4, decimal_places=2, default='0.0')
    committee = models.ForeignKey(
        ReviewTrack, related_name='committee', verbose_name="PRC Member", null=True, on_delete=models.SET_NULL
    )
    comments = models.TextField(blank=True, null=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return "{}, {}{}".format(self.user.last_name, self.user.first_name, ' *' if self.committee else '')

    def institution(self):
        return self.user.institution

    def reviews(self):
        return self.user.reviews.all()

    def cycle_reviews(self, cycle):
        return self.reviews().filter(cycle=cycle)

    def committee_proposals(self, cycle):
        if self.committee:
            return cycle.submissions.filter(track=self.committee, reviews__reviewer=self.user).distinct()

    def technique_names(self):
        return ', '.join(self.techniques.values_list('name', flat=True))

    technique_names.short_description = 'Techniques'
    technique_names.sort_field = 'techniques__name'

    def area_names(self):
        return ', '.join(self.areas.values_list('name', flat=True))

    area_names.short_description = 'Subject Areas'
    area_names.sort_field = 'areas__name'

    class Meta:
        ordering = ('user__last_name',)


class ReviewQueryset(GenericContentQueryset):
    def scientific(self):
        return self.filter(type__code__in=USO_SCIENCE_REVIEWS).order_by('reviewer__reviewer__committee')

    def technical(self):
        return self.filter(type__code__in=USO_TECHNICAL_REVIEWS)

    def safety(self):
        return self.filter(type__code__in=USO_SAFETY_REVIEWS)

    def complete(self):
        return self.filter(state__gte=Review.STATES.submitted)

    def pending(self):
        return self.filter(state__lt=Review.STATES.submitted)

    def by_type(self):
        return self.order_by('type')

    def scored(self):
        return self.exclude(Q(type__score_fields={}) | Q(type__score_fields__isnull=True))

    def by_completeness(self):
        return self.order_by('-is_complete', 'type')

    def reviewers(self):
        """NOTE: returns a user queryset not a Review queryset"""
        return get_user_model().objects.filter(pk__in=self.values_list('reviewer__pk', flat=True))

    def score_summary(self):
        return {
            score['type__code']: score['score__avg']
            for score in self.scored().values('type__code').annotate(Avg('score')).order_by('type__code')
        }


class ReviewTypeQueryset(models.QuerySet):
    def safety(self):
        return self.filter(code__in=USO_SAFETY_REVIEWS)

    def safety_approval(self):
        return self.filter(code=USO_SAFETY_APPROVAL)

    def technical(self):
        return self.filter(code__in=USO_TECHNICAL_REVIEWS)

    def scientific(self):
        return self.filter(code__in=USO_SCIENCE_REVIEWS)

    def scored(self):
        return self.exclude(Q(score_fields={}) | Q(score_fields__isnull=True))

    def with_scores(self):
        """
        Calculate average and standard deviations of each review type
        :return:
        """
        annotations = {}
        for rev_type in ReviewType.objects.scored():

            annotations[f"{rev_type.code}_avg"] = Avg(
                Case(
                    When(Q(reviews__is_complete=True, reviews__type=rev_type), then=F('reviews__score')),
                    output_field=models.FloatField()
                )
            )
            annotations[f"{rev_type.code}_std"] = StdDev(
                Case(
                    When(Q(reviews__is_complete=True, reviews__type=rev_type), then=F('reviews__score')),
                    output_field=models.FloatField()
                )
            )
        return self.annotate(**annotations).distinct()


class ReviewType(TimeStampedModel):
    code = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    form_type = models.ForeignKey(FormType, on_delete=models.CASCADE, null=True)
    score_fields = models.JSONField(default=dict, blank=True, null=True)
    role = models.CharField(max_length=100, null=True, blank=True)
    objects = ReviewTypeQueryset.as_manager()

    def __str__(self):
        return self.description.strip()

    def is_safety(self):
        return self.code in USO_SAFETY_REVIEWS + [USO_SAFETY_APPROVAL]


class Review(DynEntryMixin, GenericContentMixin):
    STATES = Choices(
        (0, 'pending', 'Pending'), (1, 'open', 'Open'), (2, 'submitted', 'Submitted'), (3, 'closed', 'Closed'), )
    reviewer = models.ForeignKey(User, related_name='reviews', null=True, on_delete=models.SET_NULL)
    role = models.CharField(max_length=100, null=True, blank=True)
    state = models.IntegerField(choices=STATES, default=STATES.pending)
    score = models.FloatField(default=0)
    due_date = models.DateField(null=True)
    cycle = models.ForeignKey(ReviewCycle, verbose_name=_('Cycle'), related_name='reviews', on_delete=models.CASCADE)
    type = models.ForeignKey(ReviewType, on_delete=models.CASCADE, related_name='reviews')

    objects = ReviewQueryset.as_manager()

    def __str__(self):
        return f"{self.reference} - {self.type}"

    def title(self):
        return f'{self.type} of {self.content_type.name.title()} {self.reference}'

    def assigned_to(self):
        if self.reviewer:
            return self.reviewer.get_full_name()
        else:
            name, realm = (self.role, '') if ':' not in self.role else self.role.split(':')
            if realm:
                return f"{name.replace('-', ' ').title()} ({realm.upper()})"
            else:
                return name.replace('-', ' ').title()

    def is_claimable(self):
        return self.role not in [None, ""]

    def is_submitted(self):
        return self.state == self.STATES.submitted

    def comments(self):
        if self.state == self.STATES.pending:
            return ""
        comments = self.details.get('comments', '').strip()
        if self.details.get('comments_committee', '').strip():
            comments = comments + "\n\n" + "<em class='text-danger'>{}</em>".format(
                self.details['comments_committee'].strip()
            )
        return comments


# Aliases
Cycle = ReviewCycle
Track = ReviewTrack
