import copy
import uuid
from collections import defaultdict
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
from dynforms.models import BaseFormModel, FormType
from model_utils import Choices
from model_utils.models import TimeStampedModel

from beamlines.models import Facility
from misc.fields import StringListField
from misc.models import Clarification, GenericContentMixin, GenericContentQueryset
from misc.models import DateSpanMixin, DateSpanQuerySet, Attachment
from publications.models import SubjectArea
from . import utils


User = getattr(settings, "AUTH_USER_MODEL")


class Proposal(BaseFormModel):
    STATES = Choices(
        (0, 'draft', 'Not Submitted'),
        (1, 'submitted', 'Submitted')
    )
    code = models.SlugField(unique=True, default=uuid.uuid4, editable=False)
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

    def is_editable(self) -> bool:
        return self.state == self.STATES.draft

    def authors(self) -> str:
        """
        Return a text representing the authors in the format 'Last, First' for each team member
        """
        return " · ".join([f"{member['last_name']}, {member['first_name']}" for member in self.get_members()])

    def __str__(self):
        title = self.title if self.title else 'No title'
        short_title = title if len(title) <= 52 else title[:52] + '..'
        return f"{self.pk} - {short_title}"

    def get_absolute_url(self):
        reverse('proposal-detail', kwargs={'pk': self.pk})

    def get_members(self) -> list[dict]:
        """
        Return a unique list of team members including everyone with team roles ('leader', 'delegate' and
        'spokesperson'). The team roles for each member will be in the key 'roles' which is a list
        """

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
        """
        Gets the user object for the delegate of this proposal, if one exists.
        :return: User object or None if no delegate is set
        """
        return get_user_model().objects.filter(username=self.delegate_username).first()

    def get_leader(self):
        """
        Returns the user object for the leader of this proposal, if one exists.
        :return: User object or None if no leader is set
        """
        return get_user_model().objects.filter(username=self.leader_username).first()

    @staticmethod
    def get_registered_member(info: dict):
        """
        Takes a user dictionary with an 'email' key and returns the user object if one exists
        :param info: member dictionary containing 'email' key
        :return: User object or None if no user with that email exists
        """
        email = info['email'].strip()
        if email:
            return get_user_model().objects.filter(
                models.Q(email__iexact=email) | models.Q(alt_email__iexact=email)
            ).first()
        return None

    def get_document(self) -> dict:
        """
        Returns a dictionary of review content for this submission.
        """
        return {
            'title': self.title,
            'authors': self.authors(),
            'topics': self.areas.all(),
            'keywords': [text.strip() for text in self.details.get('subject', {}).get('keywords', '').split(';')],
            'science': self.details,
            'safety': {
                'samples': self.details.get('sample_list', []),
                'equipment': [eq for eq in self.details.get('equipment', []) if eq],
                'handling': self.details.get('sample_handling', ''),
                'waste': self.details.get('waste_generation', []),
                'disposal': self.details.get('disposal_procedure', ''),
            },
            'attachments': self.attachments,
        }

    def hazards(self) -> QuerySet:
        """
        Returns a list of hazards associated with this proposal.
        """
        from samples.models import Sample, Hazard
        sample_ids = [item['sample'] for item in self.details.get('sample_list', [])]
        hazard_ids = set(Sample.objects.filter(pk__in=sample_ids).values_list('hazards__pk', flat=True))
        return Hazard.objects.filter(
            Q(pk__in=hazard_ids) | Q(pictograms__id__in=self.details.get('sample_hazards', []))
        ).distinct()


class SubmissionQuerySet(QuerySet):

    def with_scores(self):
        """
        Calculate average and standard deviations of each review type
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


class AccessPool(TimeStampedModel):
    """
    A pool of beam time that can accessed by projects.
    """
    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(null=True, blank=True)
    role = models.CharField(max_length=128, blank=True, null=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ['is_default']

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

    proposal = models.ForeignKey(Proposal, related_name='submissions', on_delete=models.CASCADE)
    code = models.SlugField(unique=True, default=uuid.uuid4, editable=False)
    pool = models.ForeignKey(AccessPool, related_name='submissions', on_delete=models.SET_DEFAULT, default=1)
    track = models.ForeignKey('ReviewTrack', on_delete=models.CASCADE, related_name='submissions')
    cycle = models.ForeignKey("ReviewCycle", on_delete=models.CASCADE, related_name='submissions')
    state = models.IntegerField(choices=STATES.choices, default=STATES.pending)
    approved = models.BooleanField(null=True, blank=True)
    techniques = models.ManyToManyField('ConfigItem', blank=True, related_name='submissions')
    reviews = GenericRelation('proposals.Review')
    comments = models.TextField(blank=True)
    objects = SubmissionQuerySet.as_manager()

    def reviewer(self):
        return get_user_model().objects.filter(
            pk__in=self.reviews.filter(reviewer__reviewer__committee=self.track).values_list('reviewer', flat=True)
        ).order_by('?').first()

    def __str__(self):
        return f'{self.code}~{self.proposal.spokesperson.last_name}'

    def get_absolute_url(self):
        return reverse('submission-detail', kwargs={'pk': self.pk})

    def title(self):
        return self.proposal.title

    def spokesperson(self):
        return self.proposal.spokesperson

    def siblings(self) -> QuerySet:
        """
        Get a queryset of all other submissions for the same proposal.
        """
        return self.proposal.submissions.exclude(pk=self.pk)

    def facilities(self) -> QuerySet:
        """
        Get a queryset of facilities associated with this submission.
        """
        return Facility.objects.filter(pk__in=self.techniques.values_list('config__facility', flat=True)).distinct()

    def scores(self) -> dict:
        """
        Generate a summary of review scores for this submission. The result is a dictionary with keys
        corresponding to the review stage, per-facility review stages will have a further level keyed with facility ids
        """
        facility_scores = defaultdict(list)
        acronyms = dict(self.facilities().values_list('pk', 'acronym'))

        # fetch score information from all completed reviews
        review_scores = self.reviews.complete().annotate(
            position=F('stage__position'),
            facility=F('details__facility'),
        ).order_by('position', 'facility').annotate(
            score_avg=Avg('score'),
            score_std=StdDev('score'),
        ).values(
            'position',
            'score',
            'stage',
            'facility',
            'score_avg',
            'score_std',
        )

        stages = self.track.stages.in_bulk()

        # create a dictionary mapping stage objects to score information
        for entry in review_scores:
            facility_scores[stages.get(entry['stage'], None)].append(entry)

        summary = {}
        for stage, stage_scores in facility_scores.items():
            if stage.kind.per_facility:
                # collect review scores per facility
                summary[stage] = {
                    acronyms[int(item['facility'])]: stage.add_passage(item)
                    for item in stage_scores
                }
            else:
                summary[stage] = stage.add_passage(stage_scores[0])

        return summary

    def get_facility_scores(self, passing_only=False) -> dict:
        """
        Generate a summary of review scores for this submission, grouped by facility. Each facility
        gets its own scores, per facility scores are separate, the rest are shared

        :param passing_only: If True, only return scores for facilities that passed all review stages
        """
        all_scores = self.scores()

        # each facility gets its own scores, per facility scores are separate, the rest are shared
        facility_scores = {
            facility: {
                stage: stage_score.get(facility.acronym, stage_score)
                for stage, stage_score in all_scores.items()
            }
            for facility in self.facilities()
        }

        if passing_only:
            passing = {}
            for facility, scores in facility_scores.items():
                for stage, stage_score in scores.items():
                    if stage.blocks and not stage_score.get("passed"):
                        break
                else:
                    # if we didn't break, it means all stages passed
                    passing[facility] = scores
            return passing

        return facility_scores

    def get_score_distribution(self) -> dict:
        """
        Returns a dictionary of score distributions for each review stage.
        Keys are stage objects, and values are lists of scores for that stage.
        """

        return {
            stage: list(stage.reviews.filter(is_complete=True).values_list('score', flat=True))
            for stage in self.track.stages.all()
        }

    def get_samples(self) -> QuerySet:
        """
        Returns a list of samples associated with this submission/material.
        """
        from samples.models import Sample
        sample_ids = [item['sample'] for item in self.proposal.details.get('sample_list', [])]
        return Sample.objects.filter(pk__in=sample_ids)

    def get_requests(self) -> dict:
        """
        Returns a dictionary of beamline requests associated with this submission.
        They keys facility objects, and are dictionaries containing the following keys:
        - techniques: queryset of configs requested for this facility
        - shifts: number of shifts requested for this facility
        - procedure: sample handling procedure for this facility
        - justification: justification for this facility
        """

        proposal_requests = {
            item['facility']: item
            for item in self.proposal.details.get('beamline_reqs', [])
        }
        facility_requests = {}
        for facility in self.facilities():
            req = proposal_requests.get(facility.pk, {})
            facility_requests[facility] = {
                'shifts': req.get('shifts', 0),
                'techniques': self.techniques.filter(config__facility=facility),
                'procedure': req.get('procedure', ''),
                'justification': req.get('justification', ''),
            }
        return facility_requests

    def get_document(self) -> dict:
        """
        Returns a dictionary of content for this submission. This is used to display the
        proposal in the review system.
        """

        doc = copy.deepcopy(self.proposal.get_document())

        # Update facilities and techniques as those are likely different for the submission
        facilities = self.facilities().values_list('pk', flat=True)
        proposal_reqs = doc['science']['beamline_reqs']
        doc['science']['beamline_reqs'] = []
        for req in proposal_reqs:
            facility_id = req.get('facility', 0)
            if facility_id not in facilities:
                continue
            doc['science']['beamline_reqs'].append({
                **req,
                'techniques': list(
                    self.techniques.filter(config__facility=facility_id).values_list('technique__pk', flat=True)
                )
            })
        return doc

    def get_comments(self) -> str:
        """
        Extract reviewer comments from completed reviews
        """
        all_comments = self.reviews.complete().values_list('stage__kind__description', 'details__comments')
        counts = defaultdict(int)
        texts = []
        for name, comments in all_comments:
            if not comments:
                continue
            counts[name] += 1
            texts.append(
                f"**{name} #{counts[name]}**: {comments}\n"
            )
        return "\n".join(texts)

    title.sort_field = 'proposal__title'
    facilities.sort_field = 'techniques__config__facility__acronym'
    spokesperson.sort_field = 'proposal__spokesperson__first_name'

    class Meta:
        unique_together = ("proposal", "track")


class ReviewTrack(TimeStampedModel):
    """
    A review track represents a series of stages that a proposal must go through during the review process.
    Each track can have multiple stages, and each stage can have a different review and reviewers.
    """
    name = models.CharField(max_length=128)
    acronym = models.CharField(max_length=10, unique=True)
    description = models.TextField(null=True)
    require_call = models.BooleanField("Require Call", default=True)
    notify_offset = models.IntegerField("Notify After", default=1)
    duration = models.IntegerField("Project Cycles", default=4)

    def __str__(self):
        return f"{self.acronym} - {self.name}"

    def stage_progress(self, cycle: 'ReviewCycle') -> list[dict]:
        """
        Return a dictionary of the progress of each stage in the track for the given cycle
        :param cycle: ReviewCycle
        :return: List of dictionaries with stage information per stage, keys are:
            - 'stage': stage position
            - 'count': total number of reviews
            - 'complete': number of completed reviews
        """
        return list(Review.objects.filter(cycle=cycle, stage__track=self).values('stage').annotate(
            count=Count('stage'), complete=Count('stage', filter=Q(state=Review.STATES.submitted))
        ))


class ReviewCycleQuerySet(DateSpanQuerySet):

    def archived(self) -> QuerySet:
        """
        Return the queryset representing all cycles that are archived.
        """
        return self.filter(state=ReviewCycle.STATES.archive)

    def pending(self, dt: datetime = None) -> QuerySet:
        """
        Return the queryset representing all cycles with an start_date in the future
        :param dt: Optional date to filter from, defaults to today
        """
        dt = timezone.now().date() if not dt else dt
        return self.filter(Q(open_date__gt=dt))

    def open(self) -> QuerySet:
        """
        Return the queryset representing all objects in the open state.
        """
        return self.filter(state=ReviewCycle.STATES.open)

    def next_call(self, dt: datetime = None):
        """
        Return the next review cycle that is open or pending, starting from the given date.
        :param dt: Optional date to filter from, defaults to today
        :return: ReviewCycle or None if no cycle is found
        """
        dt = timezone.now().date() if not dt else dt
        return self.filter(open_date__gte=dt).first()

    def review(self) -> QuerySet:
        """
        Return the queryset representing all objects in the review state.
        """
        return self.filter(state=ReviewCycle.STATES.review)

    def evaluation(self) -> QuerySet:
        """
        Return the queryset representing all objects in the evaluation state.
        """
        return self.filter(state=ReviewCycle.STATES.evaluation)

    def schedule(self) -> QuerySet:
        """
        Return the queryset representing all objects in the scheduling state.
        """
        return self.filter(state=ReviewCycle.STATES.schedule)


class ReviewCycle(DateSpanMixin, TimeStampedModel):
    """
    A review cycle represents a period during which proposals are reviewed and evaluated, as well as the
    scheduling of beamtime for successful proposals.,
    """
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
    objects = ReviewCycleQuerySet.as_manager()

    def configs(self) -> QuerySet:
        """
        Get the queryset of all active facility configurations for this cycle.
        """
        return FacilityConfig.objects.active(d=self.start_date)

    def techniques(self):
        """
        Get a queryset of all techniques that are part of the configurations in this cycle.
        :return:
        """
        return Technique.objects.filter(pk__in=self.configs().values_list('techniques', flat=True)).distinct()

    # def tracks(self):
    #     return ReviewTrack.objects.filter(pk__in=self.submissions.values_list('track', flat=True))

    def num_submissions(self) -> int:
        """
        Get the number of submissions in this cycle.
        """
        return self.submissions.count()

    def num_facilities(self) -> int:
        """
        Get the number of facilities that have active configurations in this cycle.
        :return:
        """
        return self.configs().count()

    def is_closed(self) -> bool:
        return self.close_date < timezone.now().date()

    def is_open(self) -> bool:
        return self.state == self.STATES.open

    def last_date(self) -> date:
        """
        Get the last valid date for this cycle, which is the day before the close date.
        :return:
        """
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
    """
    A scientific technique that can be used in a facility configuration. Used by beamlines, proposals and
    reviewers. Allows for matching of proposals to beamlines and reviewers to proposals.
    """
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
        return self.name if not self.acronym else f'{self.name} ({self.acronym})'

    def short_name(self):
        """
        Get a short name for the technique, which is either the acronym or the name if no acronym is set.
        """
        return self.name if not self.acronym else self.acronym

    class Meta:
        ordering = ['category']


class FacilityConfigQueryset(models.QuerySet):

    def for_facility(self, facility, accepting=True) -> QuerySet:
        """
        Return the queryset representing all objects accepting proposals for a given facility.
        :param facility: Facility object or id
        :param accepting: If True, only return configurations that are accepting proposals,
        otherwise if false, only those not accepting, if None, return all configurations for the facility.
        """
        if accepting in [True, False]:
            filters = {'facility': facility, 'accept': accepting}
        else:
            filters = {'facility': facility}
        return self.filter(**filters).order_by('start_date')

    def get_for_cycle(self, cycle) -> QuerySet:
        """
        Return the queryset representing all objects for a given cycle.
        """
        if isinstance(cycle, int):
            cycle = ReviewCycle.objects.get(pk=cycle)

        return self.filter(
            Q(cycle=cycle) | Q(start_date__lte=cycle.start_date)
        ).order_by('start_date').last()

    def active(self, year=None, d=None) -> QuerySet:
        """
        Get the active configurations for a given date or year.
        :param year: Either a year or None
        :param d: a date object or None, if None, the current date is used.
        :return: a queryset of active configurations.
        """

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

    def accepting(self) -> QuerySet:
        """
        Select subset of configurations that are accepting proposals.
        """
        return self.filter(accept=True)

    def pending(self, d: date = None) -> QuerySet:
        """
        Select subset of configurations that are pending, i.e. start date is in the future relative to a given
        date or the current date, if no date is given.
        """
        if not d:
            d = timezone.now().date()
        return self.filter(start_date__gt=d)

    def expired(self, year: int = None, d: date = None) -> QuerySet:
        """
        Select subset of configurations that are expired, relative to the given year or date. That is they were active
        in the past but another configuration is more current on that date.
        :param year: Optional year
        :param d: Optional date, if not given, the current date is used.
        """
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
    """
    A configuration for a facility that defines the techniques available, the track they are associated with.
    and the effective cycle or start date
    """
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

    def is_active(self) -> bool:
        """
        Check if this configuration is active, i.e. it is the latest configuration for the facility
        """
        return FacilityConfig.objects.filter(facility=self.facility, pk=self.pk).active().exists()

    def is_editable(self) -> bool:
        """
        Check if this configuration is editable, i.e. it is not part of an open cycle.
        """
        if self.cycle:
            return self.cycle.open_date > timezone.now().date()
        return False

    def siblings(self):
        """
        Get a queryset of all other configurations for the same facility that are not this one.
        """
        return FacilityConfig.objects.filter(facility=self.facility).exclude(pk=self.pk)


class ConfigItemQueryset(models.QuerySet):
    def group_by_track(self):
        return {track: self.filter(track=track) for track in ReviewTrack.objects.all()}


class ConfigItem(TimeStampedModel):
    """
    A model that connects a FacilityConfig with a Technique and a ReviewTrack.
    """
    config = models.ForeignKey(FacilityConfig, related_name="items", on_delete=models.CASCADE)
    technique = models.ForeignKey(Technique, related_name="items", on_delete=models.CASCADE)
    track = models.ForeignKey("ReviewTrack", on_delete=models.CASCADE)
    objects = ConfigItemQueryset.as_manager()

    class Meta:
        unique_together = [("config", "technique", "track")]

    def __str__(self):
        return f"{self.config}/{self.track.acronym}/{self.technique.short_name()}"


class ReviewerQueryset(models.QuerySet):
    def available(self, cycle=None) -> QuerySet:
        """
        Get a queryset of reviewers that are available for the given cycle.
        :param cycle: Optional ReviewCycle object, if not given, the current date is used to determine availability.
        """
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

    def committee(self) -> QuerySet:
        """
        Get a queryset of reviewers that are part of a committee, i.e. have a non-null committee field.
        """
        return self.filter(committee__isnull=False)


class Reviewer(TimeStampedModel):
    """
    A reviewer is a user who can review proposals. They are associated with techniques and subject areas.
    """
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

    def is_suspended(self, dt: datetime = None) -> bool:
        """
        Check if the reviewer is suspended relative to a given date, i.e. they have opted out of reviewing
        for more than a year.
        :param dt: optional datetime to check against, if not given, the current date is used.
        """
        dt = timezone.now() if not dt else datetime.combine(dt, datetime.min.time())
        expiry = (dt - timedelta(days=364)).date()
        return self.declined is not None and self.declined >= expiry

    def institution(self):
        """
        Get the reviewer's institution.
        :return: Institution object or None if the user has no institution set.
        """
        return self.user.institution

    def reviews(self) -> QuerySet:
        """
        Get a queryset of all reviews for this reviewer.
        """
        return self.user.reviews.all()

    def cycle_reviews(self, cycle) -> QuerySet:
        """
        Get a queryset of all reviews for this reviewer in a given cycle.
        :param cycle: target cycle
        """
        return self.reviews().filter(cycle=cycle)

    def committee_proposals(self, cycle: ReviewCycle) -> QuerySet:
        """
        Get a queryset of all proposals that this reviewer has reviewed this cycle as a committee member.
        :param cycle: Target cycle
        :return: An empty queryset if the reviewer is not part of a committee
        """
        if self.committee:
            return cycle.submissions.filter(track=self.committee, reviews__reviewer=self.user).distinct()
        return Submission.objects.none()

    def topic_names(self) -> str:
        """
        Get text representation of the techniques and subject areas this reviewer is associated with.
        """
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

    def area_names(self) -> str:
        """
        Get a comma-separated list of subject areas this reviewer is associated with.
        """
        return ', '.join(self.areas.values_list('name', flat=True))

    # descriptors for display in itemlist
    topic_names.short_description = 'Topics'
    topic_names.sort_field = 'techniques__name'
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
        return self.filter(is_complete=True)

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
    """
    A type of review that can be performed. Each type points to the form type used for the review, the
    role of reviewers responsible for this review, the fields that are scored in the review,
    whether lower scores are better, and if the review is per facility.
    """
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
    """
    A review stage within a review track. Each stage is associated with a review type and has all
    the information needed to determine of the review was successful or not, such as minimum reviews required,
    maximum workload, whether it blocks passage to the next stage, and the passing score.
    """
    track = models.ForeignKey(_('ReviewTrack'), on_delete=models.CASCADE, related_name='stages')
    kind = models.ForeignKey(ReviewType, on_delete=models.CASCADE, related_name='stages')
    position = models.IntegerField(_("Position"), default=0)
    min_reviews = models.IntegerField("Minimum Reviews", default=1)
    max_workload = models.IntegerField("Max Workload", default=0)
    blocks = models.BooleanField(_("Block Passage"), default=True)
    pass_score = models.FloatField(_("Passing Score"), null=True, blank=True)
    weight = models.FloatField(_("Weight"), default=1.0)
    auto_create = models.BooleanField(_("Auto Create"), default=True)
    auto_start = models.BooleanField(_("Auto Start"), default=True)
    objects = ReviewStageQuerySet.as_manager()

    class Meta:
        unique_together = ('track', 'kind')
        ordering = ('track', 'position')

    def __str__(self):
        return f"{self.track.acronym} - Stage {self.position}"

    def add_passage(self, info: dict) -> dict:
        """
        Add passage data to the score information.
        :param info: Dictionary containing the score information. A 'score_avg' or 'score' key is expected.
        :return: Updated info dictionary with a boolean `passed` key added
        """

        if 'score_avg' not in info and not 'score' in info:
            return info

        score = info.get('score_avg', info.get('score', 0.0))
        return {
            **info,
            'passed': (score <= self.pass_score) if self.kind.low_better else (score >= self.pass_score)
        }


class Review(BaseFormModel, GenericContentMixin):
    """
    A review object. It links to a generic reference object, making it possible to attach reviews to a wide
    variety of object types. Currently, "Submission" and "Material".
    """
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

    def title(self) -> str:
        """
        Get a title for this review, which is a string representation of the type and content type.
        """
        return f'{self.type} of {self.content_type.name.title()} {self.reference}'

    def assigned_to(self) -> str:
        """
        Get a string representation of the reviewer or the role if no reviewer is assigned.
        """
        if self.reviewer:
            return self.reviewer.get_full_name()
        else:
            name, realm = (self.role, '') if ':' not in self.role else self.role.split(':')
            if realm:
                return f"{name.replace('-', ' ').title()} ({realm.upper()})"
            else:
                return name.replace('-', ' ').title()

    def is_claimable(self):
        """
        Check if this review can be claimed by a reviewer.
        """
        return self.role not in [None, ""]

    def is_submitted(self) -> bool:
        """
        Check if this review is in the submitted state.
        """
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
