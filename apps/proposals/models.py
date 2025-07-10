import os
from datetime import date, timedelta, datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models import Case, Avg, When, F, Q, StdDev, Max, Count
from django.db.models.query import QuerySet
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from model_utils import Choices
from model_utils.models import TimeStampedModel

from beamlines.models import Facility
from dynforms.models import BaseFormModel, FormType
from misc.fields import StringListField
from misc.models import DateSpanMixin, DateSpanQuerySet, Attachment, Clarification, GenericContentMixin, \
    GenericContentQueryset
from misc.utils import debug_value
from publications.models import SubjectArea

User = getattr(settings, "AUTH_USER_MODEL")
USO_SAFETY_APPROVAL = getattr(settings, "USO_SAFETY_APPROVAL", 'approval')


def _proposal_filename(instance, filename):
    ext = os.path.splitext(filename)[-1]
    return os.path.join('proposals', str(instance.proposal.pk), instance.slug + ext)


class Proposal(BaseFormModel):
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

        leader_email = self.details.get('leader', {}).get('email', '').strip().lower()
        spokesperson_email = self.spokesperson.email.strip().lower()
        spokesperson_roles = ['spokesperson'] + ['leader'] if spokesperson_email == leader_email else []

        full_team = {
            spokesperson_email: {
                'first_name': self.spokesperson.first_name,
                'last_name': self.spokesperson.last_name,
                'email': self.spokesperson.email.strip().lower(),
                'roles': spokesperson_roles
            }
        }
        delegate_email = self.details.get('delegate', {}).get('email', '').strip().lower()
        if delegate_email and delegate_email != spokesperson_email:
            delegate = self.details.get('delegate', {})
            full_team[delegate_email] = {
                'first_name': delegate.get('first_name', ''),
                'last_name': delegate.get('last_name', ''),
                'email': delegate_email,
                'roles': ['delegate']
            }
        for member in self.details.get('team_members', []):
            email = member.get('email', '').strip().lower()
            if email not in full_team:
                full_team[email] = {
                    'first_name': member.get('first_name', ''),
                    'last_name': member.get('last_name', ''),
                    'email': email,
                    'roles': []
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

    def authors_text(self):
        """
        Return a text representing the authors in the format 'Last, First' for each team member
        """
        authors = []
        for member in self.get_full_team():
            authors.append(f"{member['last_name']}, {member['first_name']}")
        return " · ".join(authors)

    def get_review_content(self):
        """
        Returns a dictionary of review content for this submission.
        """
        return {
            'title': self.title,
            'authors': self.authors_text(),
            'science': self.details,
            'safety': {
                'samples': self.details.get('sample_list', []),
                'equipment': self.details.get('equipment', []),
                'handling': self.details.get('sample_handling', ''),
                'waste': self.details.get('waste_generation', []),
                'disposal': self.details.get('disposal_procedure', ''),
            },
            'attachments': self.attachments,
        }

    def hazards(self):
        """
        Returns a list of hazards associated with this proposal.
        """
        from samples.models import Sample, Hazard
        sample_ids = [item['sample'] for item in self.details.get('sample_list', [])]
        hazard_ids = Sample.objects.filter(pk__in=sample_ids).values_list('hazards__pk', flat=True)
        return Hazard.objects.filter(pk__in=hazard_ids)


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
                    When(Q(reviews__state__gte=Review.STATES.submitted, reviews__type=rev_type),
                         then=F('reviews__score')),
                    output_field=models.FloatField()
                )
            )
            annotations[f"{rev_type.code}_std"] = StdDev(
                Case(
                    When(Q(reviews__state__gte=Review.STATES.submitted, reviews__type=rev_type),
                         then=F('reviews__score')),
                    output_field=models.FloatField()
                )
            )
        return self.annotate(**annotations).distinct()


from django.db.models.functions import Concat
from misc.functions import String, LPad

_submission_code_func = Concat(
    'track__acronym', LPad(
        String('proposal_id'), 6
    ), output_field=models.CharField()
)


class AccessPool(TimeStampedModel):
    """
    A pool of beam time that can accessed by projects.
    """
    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(null=True, blank=True)
    role = models.CharField(max_length=128, blank=True, null=True)
    is_default = models.BooleanField(default=False)

    def delete(self, using=None, keep_parents=False):
        """
        Override delete to prevent deletion of default access pool.
        """
        if self.is_default:
            raise ValueError("Cannot delete the default access pool.")
        super().delete(using=using, keep_parents=keep_parents)

    def __str__(self):
        return self.name


class Submission(TimeStampedModel):
    class STATES(models.IntegerChoices):
        pending = (0, 'Pending')
        started = (1, 'Started')
        reviewed = (2, 'Reviewed')
        complete = (3, 'Complete')

    class TYPES(models.TextChoices):
        user = ('user', 'General Access')
        staff = ('staff', 'Staff Access')
        purchased = ('purchased', 'Purchased Access')
        beamteam = ('beamteam', 'Beam Team')
        education = ('education', 'Education/Outreach')

    proposal = models.ForeignKey(Proposal, related_name='submissions', on_delete=models.CASCADE)
    pool = models.ForeignKey(AccessPool, related_name='submissions', on_delete=models.SET_DEFAULT, default=1)
    track = models.ForeignKey('ReviewTrack', on_delete=models.CASCADE, related_name='submissions')
    cycle = models.ForeignKey("ReviewCycle", on_delete=models.CASCADE, related_name='submissions')
    state = models.IntegerField(choices=STATES.choices, default=STATES.pending)
    approved = models.BooleanField(null=True, blank=True)
    techniques = models.ManyToManyField('ConfigItem', blank=True, related_name='submissions')
    reviews = GenericRelation('proposals.Review')
    comments = models.TextField(blank=True)
    objects = SubmissionQuerySet.as_manager()

    def code(self):
        return f'{self.track.acronym}{self.proposal.pk:0>6}'

    def reviewer(self):
        return get_user_model().objects.filter(
            pk__in=self.reviews.filter(reviewer__reviewer__committee=self.track).values_list('reviewer', flat=True)
        ).order_by('?').first()

    def __str__(self):
        return '{}~{}'.format(
            self.code(), self.proposal.spokesperson.last_name, )

    def get_absolute_url(self):
        return reverse('submission-detail', kwargs={'pk': self.pk})

    def update_state(self):
        pass

    def title(self):
        return self.proposal.title

    def spokesperson(self):
        return self.proposal.spokesperson

    def siblings(self):
        return self.proposal.submissions.exclude(pk=self.pk)

    def facilities(self):
        return Facility.objects.filter(pk__in=self.techniques.values_list('config__facility', flat=True)).distinct()

    code.sort_field = 'id'
    title.sort_field = 'proposal__title'
    facilities.sort_field = 'techniques__config__facility__acronym'
    spokesperson.sort_field = 'proposal__spokesperson__first_name'

    def scores(self):
        summary = self.reviews.score_summary()
        summary['facilities'] = {
            int(r.details.get('requirements', {}).get('facility', 0)): r.score
            for r in self.reviews.technical().complete()
        }
        return summary

    def get_samples(self):
        """
        Returns a list of samples associated with this material.
        """
        from samples.models import Sample
        sample_ids = [item['sample'] for item in self.proposal.details.get('sample_list', [])]
        return Sample.objects.filter(pk__in=sample_ids)

    def get_review_content(self):
        """
        Returns a dictionary of review content for this submission.
        """
        return self.proposal.get_review_content()

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
        return f'{self.submission} Score Adjustment: {self.value:+}'


class ReviewTrack(TimeStampedModel):
    name = models.CharField(max_length=128)
    acronym = models.CharField(max_length=10, unique=True)
    description = models.TextField(null=True)
    require_call = models.BooleanField("Require Call", default=True)
    notify_offset = models.IntegerField("Notify After", default=1)
    duration = models.IntegerField("Project Cycles", default=4)

    def __str__(self):
        return f"{self.acronym} - {self.name}"

    def stage_progress(self, cycle):
        """
        Return a dictionary of the progress of each stage in the track for the given cycle
        :param cycle: ReviewCycle
        :return:
        """
        return Review.objects.filter(cycle=cycle, stage__track=self).values('stage').annotate(
            count=Count('stage'), complete=Count('stage', filter=Q(state=Review.STATES.submitted))
        )


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
        (0, 'pending', _('Call Pending')),
        (1, 'open', _('Call Open')),
        (2, 'assign', _('Assigning')),
        (3, 'review', _('Review')),
        (4, 'evaluation', _('Evaluation')),
        (5, 'schedule', _('Scheduling')),
        (6, 'active', _('Active')),
        (7, 'archive', _('Archived')), )
    TYPES = Choices(
        ('mock', 'Mock Cycle'),
        ('normal', 'Normal Cycle'),
    )
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
        return FacilityConfig.objects.active(d=self.start_date)

    def techniques(self):
        return Technique.objects.filter(pk__in=self.configs().values_list('techniques', flat=True)).distinct()

    def tracks(self):
        return ReviewTrack.objects.filter(pk__in=self.submissions.values_list('track', flat=True))

    def num_submissions(self):
        return self.submissions.count()

    def num_facilities(self):
        return self.configs().count()

    def is_closed(self):
        return self.close_date < timezone.now().date()

    def is_open(self):
        return self.state == self.STATES.open

    def last_date(self):
        return self.end_date - timedelta(days=1)

    def name(self):
        return f"{self.start_date.strftime('%b')}-{self.last_date().strftime('%b')} {self.start_date.strftime('%Y')}"

    def __str__(self):
        return self.name()

    num_submissions.short_description = 'Proposals'
    num_facilities.short_description = 'Facilities'

    class Meta:
        unique_together = ("start_date", "open_date")
        get_latest_by = "start_date"


class Technique(TimeStampedModel):
    TYPES = Choices(
        ('diffraction', _('Diffraction/Scattering')),
        ('imaging', _('Imaging')),
        ('microscopy', _('Microscopy')),
        ('spectroscopy', _('Spectroscopy')),
        ('other', _('Other')),
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(_('Category'), max_length=50, choices=TYPES, default=TYPES.other)
    acronym = models.CharField(_('Acronym'), max_length=20, null=True, blank=True)
    parent = models.ForeignKey('self', related_name='children', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name if not self.acronym else '{} ({})'.format(self.name, self.acronym)

    def short_name(self):
        return self.name if not self.acronym else self.acronym

    class Meta:
        ordering = ['category']


class FacilityConfigQueryset(models.QuerySet):
    def active(self, year=None, d=None):
        if year and not d:
            d = date(year, 12, 31)
        elif not d:
            d = timezone.now().date()

        pre_extras = {'facility__configs__start_date__lte': d}
        return self.annotate(
            latest=Max(
                Case(
                    When(Q(**pre_extras), then=F('facility__configs__start_date')), output_field=models.DateField()
                )
            )
        ).filter(start_date=F('latest'))

    def accepting(self):
        return self.filter(accept=True)

    def pending(self, d=None):
        if not d:
            d = timezone.now().date()
        return self.filter(start_date__gt=d)

    def expired(self, year=None, d=None):
        if year and not d:
            d = date(year, 12, 31)
        elif not d:
            d = timezone.now().date()

        pre_extras = {'facility__configs__start_date__lte': d}
        return self.annotate(
            latest=Max(
                Case(
                    When(Q(**pre_extras), then=F('facility__configs__start_date')), output_field=models.DateField()
                )
            )
        ).filter(start_date__lt=F('latest'))


class FacilityConfig(TimeStampedModel):
    cycle = models.ForeignKey(ReviewCycle, verbose_name=_('Start Cycle'), on_delete=models.SET_NULL, null=True)
    start_date = models.DateField(_("Start Date"))
    accept = models.BooleanField("Accept Proposals", default=False)
    facility = models.ForeignKey(Facility, related_name="configs", on_delete=models.CASCADE)
    techniques = models.ManyToManyField(Technique, through="ConfigItem", related_name="configs")
    comments = models.TextField(blank=True, null=True)
    objects = FacilityConfigQueryset.as_manager()

    class Meta:
        unique_together = ("cycle", "facility")
        get_latest_by = "start_date"
        ordering = ['-start_date']
        verbose_name = "Facility Configuration"

    def __str__(self):
        if self.pk:
            return f"{self.facility.acronym}/{self.start_date.strftime('%Y-%m-%d')}"
        else:
            return "<unsaved>"

    def is_active(self):
        return FacilityConfig.objects.filter(facility=self.facility, pk=self.pk).active().exists()

    def is_editable(self):
        if self.cycle:
            return self.cycle.open_date > timezone.now().date()
        return False

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
        unique_together = [("config", "technique", "track")]

    def __str__(self):
        return f"{self.config}/{self.track.acronym}/{self.technique.short_name()}"


class ReviewerQueryset(models.QuerySet):
    def available(self, cycle=None):
        if not cycle:
            cycle_time = timezone.now()
        else:
            cycle_time = datetime.combine(cycle.open_date, datetime.min.time())

        expiry = (cycle_time - timedelta(days=364)).date()
        return self.filter(
            Q(active=True)
            & (Q(declined__isnull=True) | Q(declined__lt=expiry))
            & Q(techniques__isnull=False)
            & Q(areas__isnull=False)
        ).distinct()

    def committee(self):
        return self.filter(committee__isnull=False)


class Reviewer(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='reviewer')
    techniques = models.ManyToManyField(Technique, related_name="reviewers")
    areas = models.ManyToManyField(SubjectArea, verbose_name=_('Subject Areas'), )
    karma = models.DecimalField(max_digits=4, decimal_places=2, default='0.0')
    committee = models.ForeignKey(
        ReviewTrack, related_name='committee', verbose_name="Committee Member", null=True, on_delete=models.SET_NULL
    )
    comments = models.TextField(blank=True, null=True)
    active = models.BooleanField(default=True)
    declined = models.DateField("Opted-out", null=True, blank=True)

    objects = ReviewerQueryset.as_manager()

    def __str__(self):
        return f"{self.user.last_name}, {self.user.first_name}{' 🜲' if self.committee else ''}"

    def is_suspended(self, dt=None):
        dt = timezone.now() if not dt else datetime.combine(dt, datetime.min.time())
        expiry = (dt - timedelta(days=364)).date()
        return self.declined is not None and self.declined >= expiry

    def institution(self):
        return self.user.institution

    def reviews(self):
        return self.user.reviews.all()

    def cycle_reviews(self, cycle):
        return self.reviews().filter(cycle=cycle)

    def committee_proposals(self, cycle):
        if self.committee:
            return cycle.submissions.filter(track=self.committee, reviews__reviewer=self.user).distinct()
        return Submission.objects.none()

    def topic_names(self):
        techniques = ', '.join(self.techniques.values_list('acronym', flat=True))
        subjects = ', '.join(self.areas.values_list('name', flat=True))
        style = ''
        if not self.active:
            style = 'text-danger'
        elif self.is_suspended():
            style = 'text-warning'

        return mark_safe(
            f"<section class='{style}'><span>{techniques}</span><br>"
            f"<em>{subjects}</em></section>"
        )

    topic_names.short_description = 'Topics'
    topic_names.sort_field = 'techniques__name'

    def area_names(self):
        return ', '.join(self.areas.values_list('name', flat=True))

    area_names.short_description = 'Subject Areas'
    area_names.sort_field = 'areas__name'

    class Meta:
        ordering = ('user__last_name',)


class ReviewQueryset(GenericContentQueryset):
    def scientific(self):
        return self.filter(type__kind=ReviewType.Types.scientific).order_by('reviewer__reviewer__committee')

    def technical(self):
        return self.filter(type__kind=ReviewType.Types.technical)

    def safety(self):
        return self.filter(type__kind=ReviewType.Types.safety)

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
        return self.filter(kind=ReviewType.Types.safety)

    def safety_approval(self):
        return self.filter(kind=ReviewType.Types.approval)

    def technical(self):
        return self.filter(kind=ReviewType.Types.technical)

    def scientific(self):
        return self.filter(kind=ReviewType.Types.scientific)

    def scored(self):
        return self.exclude(Q(score_fields={}) | Q(score_fields__isnull=True))

    def with_scores(self):
        """
        Calculate average and standard deviations of each review type
        :return:
        """
        annotations = {}
        keys = self.values_list('code', flat=True)
        print('KEYS', keys)
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
    class Types(models.TextChoices):
        safety = ('safety', _('Safety Review'))
        technical = ('technical', _('Technical Review'))
        scientific = ('scientific', _('Scientific Review'))
        approval = ('approval', _('Safety Approval'))

    code = models.SlugField(max_length=100, unique=True)
    kind = models.CharField(max_length=20, choices=Types.choices, default=Types.technical)
    description = models.TextField(blank=True, null=True)
    form_type = models.ForeignKey(FormType, on_delete=models.CASCADE, null=True)
    score_fields = models.JSONField(default=dict, blank=True, null=True)
    low_better = models.BooleanField(_("Lower Score Better"), default=True)
    per_facility = models.BooleanField(_("Per Facility"), default=False)
    role = models.CharField(max_length=100, null=True, blank=True)
    objects = ReviewTypeQueryset.as_manager()

    def __str__(self):
        return self.description.strip()

    @property
    def is_scientific(self):
        return self.kind == self.Types.scientific

    @property
    def is_safety(self):
        return self.kind == self.Types.safety

    @property
    def is_approval(self):
        return self.kind == self.Types.approval

    @property
    def is_technical(self):
        return self.kind == self.Types.technical


class ReviewStageQuerySet(models.QuerySet):
    def with_stats(self):
        return self.annotate(
            avg_score=Avg('reviews__score'),
            std_dev=StdDev('reviews__score'),
            num_reviews=Count('reviews'),
            progress=Count('reviews', filter=Q(reviews__state=Review.STATES.submitted)) / Count('reviews'),
        )


class ReviewStage(TimeStampedModel):
    track = models.ForeignKey(_('ReviewTrack'), on_delete=models.CASCADE, related_name='stages')
    kind = models.ForeignKey(ReviewType, on_delete=models.CASCADE, related_name='stages')
    position = models.IntegerField(_("Position"), default=0)
    min_reviews = models.IntegerField("Minimum Reviews", default=1)
    max_workload = models.IntegerField("Max Workload", default=0)
    blocks = models.BooleanField(_("Block Passage"), default=True)
    pass_score = models.FloatField(_("Passing Score"), null=True, blank=True)
    auto_create = models.BooleanField(_("Auto Create"), default=True)
    auto_start = models.BooleanField(_("Auto Start"), default=True)
    objects = ReviewStageQuerySet.as_manager()

    def __str__(self):
        return f"{self.track.acronym} - Stage {self.position}"

    class Meta:
        unique_together = ('track', 'kind')
        ordering = ('track', 'position')


class Review(BaseFormModel, GenericContentMixin):
    STATES = Choices(
        (0, 'pending', 'Pending'),
        (1, 'open', 'Open'),
        (2, 'submitted', 'Submitted'),
        (3, 'closed', 'Closed'),
    )
    reviewer = models.ForeignKey(User, related_name='reviews', null=True, on_delete=models.SET_NULL)
    role = models.CharField(max_length=100, null=True, blank=True)
    state = models.IntegerField(choices=STATES, default=STATES.pending)
    score = models.FloatField(default=0)
    due_date = models.DateField(null=True)
    cycle = models.ForeignKey(ReviewCycle, verbose_name=_('Cycle'), related_name='reviews', on_delete=models.CASCADE)
    type = models.ForeignKey(ReviewType, on_delete=models.PROTECT, related_name='reviews')
    stage = models.ForeignKey(ReviewStage, null=True, on_delete=models.PROTECT, related_name='reviews')

    objects = ReviewQueryset.as_manager()

    def __str__(self):
        return f"{self.reference} - {self.type}"

    def get_absolute_url(self):
        url = reverse('edit-review', kwargs={'pk': self.pk})
        return f'{settings.SITE_URL}{url}'

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
        committee_comments = self.details.get('comments_committee', '').strip()
        full_comments = ""
        if comments:
            full_comments += f"<li class='text-info-emphasis'>{comments}</li>"
        if committee_comments:
            full_comments += f"<li class='text-danger-emphasis'>{committee_comments}</li>"

        return f'<ul>{full_comments}</ul>'


# Aliases
Cycle = ReviewCycle
Track = ReviewTrack
