import functools
import operator
from collections import OrderedDict
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from model_utils import Choices
from model_utils.models import TimeStampedModel, TimeFramedModel

from misc.fields import StringListField
from misc.models import DateSpanMixin, Attachment, Clarification
from proposals.models import Review, ReviewCycle
from scheduler.models import Event, EventQuerySet

User = getattr(settings, "AUTH_USER_MODEL")

PROJECT_TYPES = Choices(
    ('user', 'General Access'),
    ('staff', 'Staff Access'),
    ('maintenance', 'Maintenance/Commissioning'),
    ('purchased', 'Purchased Access'),
    ('beamteam', 'Beam Team'),
    ('education', 'Education/Outreach')
)


class Project(DateSpanMixin, TimeStampedModel):
    TYPES = PROJECT_TYPES
    proposal = models.ForeignKey('proposals.Proposal', null=True, on_delete=models.SET_NULL, related_name="project")
    submissions = models.ManyToManyField('proposals.Submission', blank=True, related_name="project")
    pool = models.ForeignKey('proposals.AccessPool', related_name='projects', on_delete=models.SET_DEFAULT, default=1)
    kind = models.CharField(_('Type'), max_length=20, choices=TYPES, default=TYPES.user)
    spokesperson = models.ForeignKey(User, related_name='+', null=True, on_delete=models.SET_NULL)
    leader = models.ForeignKey(User, related_name='+', null=True, on_delete=models.SET_NULL)
    delegate = models.ForeignKey(User, related_name='+', null=True, on_delete=models.SET_NULL)
    title = models.TextField(null=True)
    team = models.ManyToManyField('users.User', related_name="projects")
    pending_team = StringListField(blank=True, null=True)
    cycle = models.ForeignKey(
        'proposals.ReviewCycle', null=False, verbose_name=_('First Cycle'),
        related_name='projects', on_delete=models.CASCADE
    )
    techniques = models.ManyToManyField('proposals.ConfigItem', blank=True, related_name='projects')
    beamlines = models.ManyToManyField('beamlines.Facility', through='Allocation', related_name="projects")
    clarifications = GenericRelation(Clarification)
    attachments = GenericRelation(Attachment)
    tags = models.ManyToManyField('beamlines.FacilityTag', related_name="projects", blank=True)
    details = models.JSONField(default=dict, null=True, blank=True, editable=False)

    def __str__(self):
        return "{}~{}".format(
            self.code(),
            self.leader_name(),
        )

    def leader_name(self) -> str:
        """
        Get the last name of the project leader or spokesperson if the leader is not found.
        :return:
        """
        return self.get_leader().last_name

    @property
    def code(self):
        return f"{self.cycle.pk:0>2d}{self.get_kind_display()[0].upper()}{self.pk:0>5d}"

    def is_owned_by(self, user):
        return user in [self.spokesperson, self.leader, self.delegate]

    def facility_codes(self):
        return ', '.join([bl.acronym for bl in self.beamlines.distinct()])

    facility_codes.sort_field = 'beamlines__acronym'
    facility_codes.short_description = 'Facilities'

    def get_absolute_url(self):
        return reverse('project-detail', kwargs={'pk': self.pk})

    def is_pending(self, dt=None):
        dt = dt if dt else timezone.localtime(timezone.now()).date()
        return self.start_date > dt

    def state(self):
        if self.is_pending():
            return 'pending'
        else:
            return {True: 'active', False: 'inactive'}.get(self.is_active(), 'inactive')

    state.sort_field = 'end_date'

    def get_leader(self):
        return self.leader or self.spokesperson

    get_leader.short_description = "Team Leader"

    def team_members(self):
        return self.details['team_members'] or [{'first_name': '', 'last_name': '', 'email': ''}]

    def invoice_address(self):
        return self.details.get('invoice_address', {}) or {
            'place': self.get_leader().address.address_1,
            'street': self.get_leader().address.address_2,
            'city': self.get_leader().address.city,
            'region': self.get_leader().address.region,
            'country': self.get_leader().address.country,
            'code': self.get_leader().address.postal_code
        }

    def invoice_email(self):
        return self.details.get('invoice_email', None) or self.get_leader().email

    def pretty_invoice_address(self):
        address = self.invoice_address()
        return ", ".join([_f for _f in [
            address[val] for val in
            ['place', 'street', 'city', 'code', 'region', 'country']
            if address.get(val, '').strip().replace('-', '')
        ] if _f])

    pretty_invoice_address.short_description = "Invoice Address"

    def invoice_place(self):
        return self.invoice_address().get('place', '')

    def invoice_street(self):
        return self.invoice_address().get('street', '')

    def invoice_city(self):
        return self.invoice_address().get('city', '')

    def invoice_region(self):
        return self.invoice_address().get('region', '')

    def invoice_country(self):
        return self.invoice_address().get('country', '')

    def invoice_code(self):
        return self.invoice_address().get('code', '')

    def extra_team(self):
        team_emails = {u.get('email').lower(): u for u in self.details.get('team_members', {}) if u.get('email')}
        user_emails = {u.lower() for u in self.team.values_list('email', flat=True)}
        extra_emails = set(team_emails.keys()) - user_emails
        return {k: v for k, v in list(team_emails.items()) if k in extra_emails}

    def beamline_allocations(self):
        from proposals.models import Technique
        allocations = []
        this_cycle = ReviewCycle.objects.current().filter(
            start_date__lte=self.end_date, start_date__gte=self.start_date
        ).order_by('start_date').first()

        for beamline in self.beamlines.distinct():
            allocs_for_bl = self.allocations.filter(beamline=beamline)
            num_allocs = allocs_for_bl.count()
            if num_allocs == 1:
                allocation = allocs_for_bl.first()
            elif num_allocs > 1:
                allocation = allocs_for_bl.filter(cycle__start_date__lte=this_cycle.start_date).order_by(
                    '-cycle__start_date').first()
            else:
                continue
            cycle = allocation.cycle

            next_cycle = ReviewCycle.objects.next(allocation.cycle.start_date)
            totals = self.beamtimes.filter(
                beamline=beamline, start__gte=cycle.start_date, end__lte=cycle.end_date
            ).with_shifts().aggregate(scheduled=Coalesce(Sum('shifts'), 0.0))
            used_totals = self.sessions.within(
                {'start': cycle.start_date, 'end': cycle.end_date}
            ).with_shifts().aggregate(used=Coalesce(Sum('shifts'), 0.0))

            totals.update(**used_totals)

            techniques = Technique.objects.filter(
                pk__in=self.techniques.filter(
                    Q(config__facility=beamline) | Q(config__facility=beamline.parent)
                ).values_list('technique', flat=True)
            )

            allocations.append({
                'facility': beamline,
                'allocation': allocation,
                'totals': totals,
                'cycle': cycle,
                'next_cycle': next_cycle,
                'can_renew': cycle.is_open() and self.is_active() and self.is_active(
                    next_cycle.end_date) and not allocation.discretionary,
                'can_decline': self.cycle.is_pending() and allocation.shifts,
                'techniques': ", ".join([t.short_name() for t in techniques]),
                'can_request': (self.is_pending() or self.is_active()) and (
                        beamline.flex_schedule or allocation.discretionary),
                'shift_request': allocation.shift_requests.first(),
                'alloc_request': self.allocation_requests.filter(beamline=beamline, cycle=next_cycle).first(),
            })
        return allocations

    def active_allocations(self):
        return self.allocations.filter(cycle__state__lte=5)

    def current_material(self):
        material = self.materials.approved().last()
        if not material:
            material = self.materials.pending().first()
        if not material:
            material = self.materials.last()
        return material

    def used_shifts(self, bl=None):
        if bl:
            shifts = [
                s.shifts for s in
                self.sessions.filter(beamline=bl,
                                     state__in=[Session.STATES.live, Session.STATES.complete]).with_shifts()
            ]
        else:
            shifts = [
                s.shifts for s in
                self.sessions.filter(state__in=[Session.STATES.live, Session.STATES.complete]).with_shifts()
            ]
        return sum(shifts)

    def scheduled_shifts(self, bl=None):
        if bl:
            shifts = [bt.shifts for bt in self.beamtimes.filter(beamline=bl).with_shifts()]
        else:
            shifts = [bt.shifts for bt in self.beamtimes.all().with_shifts()]
        return sum(shifts)

    def permissions(self):
        # Get required permissions from approved material if it exists
        material = self.materials.approved().last()
        req_perms = set()
        any_perms = set()
        user_perms = set()
        if material:
            req_perms |= {k for k, v in list(material.permissions.items()) if v == 'all'}
            any_perms |= {k for k, v in list(material.permissions.items()) if v == 'any'}

            for s in material.samples.all():
                any_perms |= {k for k, v in list(s.permissions().items())}

        any_perms |= {'FACILITY-ACCESS'}
        beamlines = self.beamlines.exclude(kind='equipment')
        user_perms |= {'{}-USER'.format(bl.acronym) for bl in beamlines}
        user_perms |= {'{}-REMOTE-USER'.format(bl.acronym) for bl in beamlines}
        return {'all': req_perms, 'any': any_perms, 'user': user_perms}

    def scores(self, bl):
        alloc = self.allocations.filter(beamline__id=bl.pk).first()
        if alloc:
            return alloc.scores
        else:
            return {}

    def refresh_team(self, data=None):
        data = data if data else self.details

        team_data = [_f for _f in [tm for tm in data.get('team_members', [])] if _f]
        team_emails = set([_f for _f in {tm.get('email', '').lower().strip() for tm in team_data} if _f])

        if team_emails:
            query = functools.reduce(
                operator.__or__,
                [Q(email__iexact=email) | Q(alt_email__iexact=email) for email in team_emails], Q()
            )
            registered_users = set(get_user_model().objects.filter(query))
        else:
            registered_users = set()

        extras = {}
        for f in ['leader', 'delegate']:
            extras[f] = None
            if not data.get(f): continue
            email = data[f].get('email', '').lower().strip()
            if email:
                team_emails.add(email)
                user = get_user_model().objects.filter(Q(email__iexact=email) | Q(alt_email__iexact=email)).first()
                if user:
                    extras[f] = user
                    registered_users.add(user)
        registered_users.add(self.spokesperson)
        pending_emails = team_emails - {u.email.lower() for u in registered_users}

        Project.objects.filter(pk=self.pk).update(
            pending_team=pending_emails, **extras
        )
        self.team.set(registered_users)

        # Add User Role to all register team members who do have the role
        for user in self.team.all():
            user.fetch_profile()
            roles = user.get_all_roles()
            if 'user' not in roles:
                roles |= {'user'}
                user.update_profile(data={'extra_roles': list(roles)})


class MaterialQueryset(models.QuerySet):
    def pending(self):
        return self.filter(state='pending')

    def approved(self):
        return self.filter(state='approved')

    def denied(self):
        return self.exclude(state='denied')


class Material(TimeStampedModel):
    STATES = Choices(
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied')
    )
    RISKS = Choices(
        (0, 'unknown', 'Not Reviewed'),
        (1, 'low', 'Low Risk'),
        (2, 'medium', 'Moderate Risk'),
        (3, 'high', 'High Risk'),
        (4, 'unacceptable', 'Unacceptable')
    )
    project = models.ForeignKey('Project', null=False, related_name='materials', on_delete=models.CASCADE)
    samples = models.ManyToManyField('samples.Sample', through='ProjectSample', related_name='projects', blank=True)
    procedure = models.TextField(verbose_name=_('Sample Handling Procedure'))
    waste = models.JSONField(verbose_name=_('Waste Generation'), default=list)
    disposal = models.TextField(verbose_name=_('Waste Disposal'), blank=True)
    state = models.CharField(_('Status'), max_length=20, choices=STATES, default=STATES.pending)
    equipment = models.JSONField(verbose_name=_('Equipment'), default=list)
    permissions = models.JSONField(verbose_name=_('Permission Requirements'), default=dict)
    risk_level = models.IntegerField(choices=RISKS, default=RISKS.unknown)
    controls = models.ManyToManyField('samples.SafetyControl', related_name='materials', blank=True)
    reviews = GenericRelation('proposals.Review')
    objects = MaterialQueryset.as_manager()

    class Meta:
        get_latest_by = 'modified'

    def is_owned_by(self, user):
        return user in [self.project.spokesperson, self.project.leader, self.project.delegate]

    def siblings(self):
        return self.project.materials.exclude(pk=self.pk)

    def sample_list(self):
        return [{'sample': s.sample.pk, 'quantity': s.quantity} for s in self.project_samples.all()]

    def needs_ethics(self):
        sample_types = ' '.join(self.samples.values_list('kind', flat=True))
        for k in ['animal', 'human']:
            if k in sample_types:
                return True
        return False

    def get_samples(self):
        """
        Returns a list of samples associated with this material.
        """
        from samples.models import Sample
        return Sample.objects.filter(pk__in=self.samples.values_list('pk', flat=True))

    def get_review_content(self):
        """
        Returns a dictionary of review content for this submission.
        """
        author_list = []
        for member in self.project.team.all():
            roles = set()
            if member == self.project.spokesperson:
                roles.add('S')
            if member == self.project.leader:
                roles.add('L')
            if member == self.project.delegate:
                roles.add('D')
            if roles:
                author_list.append(f'{member.get_full_name()} ({", ".join(roles)})')
            else:
                author_list.append(member.get_full_name())

        authors = ", ".join(author_list)
        return {
            'title': self.project.title,
            'authors': authors,
            'science': self.project.proposal.details,
            'safety': {
                'samples': [
                    {'sample': s.sample.pk, 'quantity': s.quantity}
                    for s in self.project_samples.all()
                ],
                'equipment': self.equipment,
                'handling': self.procedure,
                'waste': self.waste,
                'disposal': self.disposal,
            },
            'attachments': self.project.attachments,
        }

    def pictograms(self):
        from samples.models import Pictogram
        from samples import utils
        hazards = self.hazards()
        hazard_types = Pictogram.objects.filter(
            pk__in=self.samples.filter(is_editable=True).values_list('hazard_types__pk', flat=True))
        return utils.summarize_pictograms(hazards, types=hazard_types)

    def hazards(self):
        from samples.models import Hazard
        hazards = Hazard.objects.filter(pk__in=self.samples.values_list('hazards__pk', flat=True))
        return hazards

    def title(self):
        return self.project.title

    @property
    def code(self):
        return "M{}/{}".format(self.project.code, self.project.pk, )

    def __str__(self):
        return self.code

    def get_absolute_url(self):
        return reverse('material-detail', kwargs={'pk': self.pk})

    def update_state(self):
        pass

    def update_due_dates(self):
        beamtime = self.project.beamtimes.filter(start__gte=timezone.now().date()).first()
        if beamtime:
            self.reviews.filter(state__lt=Review.STATES.closed, is_complete=False).update(
                due_date=beamtime.start.date() - timedelta(days=2), state=Review.STATES.open)


class SessionQueryset(EventQuerySet):
    def ready(self):
        return self.filter(state='ready')

    def live(self):
        return self.filter(state='live')

    def complete(self):
        return self.exclude(state='complete')


class Session(TimeStampedModel, TimeFramedModel):
    class STATES(models.TextChoices):
        ready = ('ready', _('Ready'))
        live = ('live', _('Active'))
        complete = ('complete', _('Complete'))
        cancelled = ('cancelled', _('Cancelled'))
        terminated = ('terminated', _('Terminated'))

    class TYPES(models.TextChoices):
        onsite = ('onsite', _('On-Site'))
        remote = ('remote', _('Remote'))
        mailin = ('mailin', _('Mail-In'))

    project = models.ForeignKey('Project', related_name='sessions', on_delete=models.CASCADE)
    beamline = models.ForeignKey('beamlines.Facility', related_name="sessions", on_delete=models.CASCADE)
    samples = models.ManyToManyField('ProjectSample', related_name='sessions', blank=True)
    team = models.ManyToManyField('users.User', related_name='sessions', verbose_name="Team Members")
    staff = models.ForeignKey('users.User', related_name="+", null=True, blank=True, on_delete=models.SET_NULL)
    spokesperson = models.ForeignKey('users.User', related_name="+", null=True, blank=True, on_delete=models.SET_NULL)
    state = models.CharField(max_length=15, choices=STATES.choices, default=STATES.ready)
    kind = models.CharField(_('Session Type'), max_length=15, choices=TYPES.choices, default=TYPES.onsite)
    details = models.JSONField(default=dict, null=True, blank=True, editable=False)

    objects = SessionQueryset.as_manager()

    def __str__(self):
        return "{}{}".format(self.beamline.acronym, timezone.localtime(self.start).strftime('%Y%m%dT%H'))

    class Meta:
        get_latest_by = 'modified'

    def is_live(self):
        now = timezone.localtime(timezone.now())
        return self.state == self.STATES.live and self.start <= now < self.end

    def is_owned_by(self, user):
        return user in self.team.all() or user in [self.spokesperson, self.staff]

    def permissions(self):
        # Get required permissions from approved material if it exists
        material = self.project.materials.approved().last()
        req_perms = set()
        any_perms = set()
        user_perms = set()
        if material:
            req_perms |= {k for k, v in list(material.permissions.items()) if v == 'all'}
            any_perms |= {k for k, v in list(material.permissions.items()) if v == 'any'}

        # Local access needs 'FACILITY-ACCESS' permissions and different USER type from Remote
        if self.kind == self.TYPES.remote:
            user_perms |= {'{}-REMOTE-USER'.format(self.beamline.parent.acronym)}
        else:
            req_perms |= {'FACILITY-ACCESS'}
            user_perms |= {'{}-USER'.format(self.beamline.acronym)}

        for s in self.samples.all():
            req_perms |= {k for k, v in list(s.sample.permissions().items()) if v == 'all'}
            any_perms |= {k for k, v in list(s.sample.permissions().items()) if v == 'any'}

        return {'all': req_perms, 'any': any_perms, 'user': user_perms}

    def sample_list(self):
        return [{'sample': s.sample.pk, 'quantity': s.quantity} for s in self.samples.all()]

    def get_full_team(self):
        project_roles = [('spokesperson', self.project.spokesperson.username),
                         ('leader', self.project.leader.username),
                         ('delegate', self.project.delegate.username)]
        full_team = {}
        registered = list(self.team.all())
        for t in set(registered):
            full_team[t.email] = {'name': t.get_full_name(),
                                  'registered': True,
                                  'classification': t.get_classification_display(),
                                  'roles': [k for k, v in project_roles if v == t.username],
                                  'photo': t.get_photo(),
                                  'permissions': {p['code']: p for p in t.permissions}}
        return OrderedDict(
            sorted(iter(full_team.items()), key=lambda x: (x[1]['roles'], x[1]['classification']), reverse=True))

    def log(self, msg, save=True):
        logs = self.details.get('history', [])
        logs.append(msg)
        self.details['history'] = logs
        if save:
            self.save()


class LabSession(TimeStampedModel, TimeFramedModel):
    STATES = Choices(
        ('pending', _('Pending')),
        ('active', _('Active')),
        ('complete', _('Complete')),
    )
    project = models.ForeignKey('Project', related_name='lab_sessions', on_delete=models.CASCADE)
    lab = models.ForeignKey('beamlines.Lab', related_name='lab_sessions', on_delete=models.CASCADE)
    workspaces = models.ManyToManyField('beamlines.LabWorkSpace', related_name='lab_sessions')
    equipment = models.ManyToManyField('beamlines.Ancillary', related_name='lab_sessions', blank=True)
    team = models.ManyToManyField('users.User', related_name='lab_sessions', verbose_name='Team Members')
    spokesperson = models.ForeignKey('users.User', related_name="+", on_delete=models.CASCADE)
    details = models.JSONField(default=dict, null=True, blank=True, editable=False)
    objects = SessionQueryset.as_manager()

    def __str__(self):
        return "{}{}".format(self.lab.acronym, timezone.localtime(self.start).strftime('%Y%m%dT%H'))

    class Meta:
        get_latest_by = 'modified'

    def is_current(self):
        now = timezone.now()
        return self.start <= now < self.end

    def is_owned_by(self, user):
        return user in self.team.all() or user == self.spokesperson

    def permissions(self):
        material = self.project.materials.approved().last()
        req_perms = set()
        any_perms = set()
        if material:
            req_perms |= {k for k, v in list(material.permissions.items()) if v == 'all'}
            any_perms |= {k for k, v in list(material.permissions.items()) if v == 'any'}

        req_perms |= set(self.lab.permissions.values_list('code', flat=True))
        req_perms |= set(self.equipment.all().values_list('permissions__code', flat=True))
        req_perms |= {'FACILITY-ACCESS'}

        return {'all': req_perms, 'any': any_perms, 'user': set()}

    def get_absolute_url(self):
        return reverse('lab-permit', kwargs={'pk': self.pk})

    def state(self):
        now = timezone.now()
        if self.start > now:
            return self.STATES.pending
        elif self.end > now:
            return self.STATES.active
        else:
            return self.STATES.complete

    def get_state_display(self):
        return self.STATES[self.state()]

    def log(self, msg, save=False):
        logs = self.details.get('history', [])
        logs.append(msg)
        self.details['history'] = logs
        if save:
            self.save()


class AllocationRequest(TimeStampedModel):
    STATES = Choices(
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('complete', 'Completed')
    )
    state = models.CharField(max_length=20, choices=STATES, default='draft')
    project = models.ForeignKey('Project', on_delete=models.CASCADE, related_name="allocation_requests")
    cycle = models.ForeignKey('proposals.ReviewCycle', on_delete=models.CASCADE, related_name="allocation_requests")
    beamline = models.ForeignKey('beamlines.Facility', on_delete=models.CASCADE, related_name="allocation_requests")
    tags = models.ManyToManyField('beamlines.FacilityTag', related_name="allocation_requests",
                                  verbose_name='Scheduling Tags')
    procedure = models.TextField(blank=True, null=True)
    justification = models.TextField(blank=True, null=True)
    shift_request = models.IntegerField('Shifts Requested', default=0)
    good_dates = models.TextField(blank=True, null=True)
    poor_dates = models.TextField(blank=True, null=True)

    def __str__(self):
        return '{} {}'.format(self.project, self.cycle)


class Allocation(TimeStampedModel):
    project = models.ForeignKey('Project', on_delete=models.CASCADE, related_name="allocations")
    cycle = models.ForeignKey('proposals.ReviewCycle', on_delete=models.CASCADE, related_name="allocations")
    beamline = models.ForeignKey('beamlines.Facility', on_delete=models.CASCADE, related_name="allocations")
    procedure = models.TextField(blank=True, null=True)
    justification = models.TextField(blank=True, null=True)
    shift_request = models.IntegerField(default=0)
    shifts = models.IntegerField(default=0)
    score = models.FloatField("Merit Score", default=0.0)
    scores = models.JSONField(default=dict, null=True, blank=True)
    declined = models.BooleanField(default=False)
    comments = models.TextField(blank=True, null=True)
    discretionary = models.BooleanField(default=False)

    class Meta:
        unique_together = ('beamline', 'cycle', 'project')

    def is_new(self):
        return self.cycle == self.project.cycle

    def is_active(self):
        active = self.cycle.STATES.evaluation <= self.cycle.state <= self.cycle.STATES.active
        return active

    def previous(self, num=4):
        return reversed(
            [self.project.allocations.filter(cycle_id=self.cycle.pk - i, beamline=self.beamline).first() for i in
             range(1, num + 1)])

    def tags(self):
        return self.project.tags.filter(Q(facility=self.beamline) | Q(facility__children=self.beamline) | Q(
            facility__parent=self.beamline)).distinct()

    def sessions(self):
        return Session.objects.filter(project=self.project, beamline=self.beamline).filter(
            Q(start__gte=self.cycle.start_date) & Q(end__lte=self.cycle.end_date))

    def __str__(self):
        return "{}:{}:{}".format(self.project, self.beamline, self.cycle)


class ShiftRequestQueryset(models.QuerySet):
    def complete(self):
        return self.filter(state='completed')

    def pending(self):
        return self.filter(state__in=['submitted', 'progress'])

    def draft(self):
        return self.filter(state='draft')

    def open(self):
        return self.exclude(state='completed')


class ShiftRequest(TimeStampedModel):
    STATES = Choices(
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('progress', 'In Progress'),
        ('completed', 'Completed')
    )
    state = models.CharField(max_length=20, choices=STATES, default='draft')
    allocation = models.ForeignKey('Allocation', on_delete=models.CASCADE, related_name="shift_requests")
    comments = models.TextField(blank=True, null=True)
    justification = models.TextField(blank=True, null=True)
    tags = models.ManyToManyField('beamlines.FacilityTag', related_name="shift_requests",
                                  verbose_name='Scheduling Tags')
    shift_request = models.IntegerField("Shifts Requested", default=0)
    good_dates = models.TextField(blank=True, null=True)
    poor_dates = models.TextField(blank=True, null=True)
    objects = ShiftRequestQueryset.as_manager()

    def __str__(self):
        return "Request {}, {}".format(self.pk, self.allocation)

    def project(self):
        return self.allocation.project

    def spokesperson(self):
        return self.project().spokesperson

    def facility(self):
        return self.allocation.beamline

    project.sort_field = 'allocation__project'
    spokesperson.sort_field = 'allocation__project__spokesperson__last_name'


class ProjectSampleQueryset(models.QuerySet):
    def by_kind(self):
        return self.order_by('sample__kind')

    def approved(self):
        return self.filter(state='approved')

    def pending(self):
        return self.filter(state='pending')

    def rejected(self):
        return self.filter(state='rejected')

    def expired(self, dt=None):
        if not dt:
            dt = timezone.now().date()
        return self.filter(expiry__lte=dt)


class ProjectSample(TimeStampedModel):
    STATES = Choices(
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired')
    )
    state = models.CharField(_('Status'), max_length=20, choices=STATES, default='pending')
    material = models.ForeignKey('Material', related_name="project_samples", on_delete=models.CASCADE)
    sample = models.ForeignKey('samples.Sample', related_name="usage", on_delete=models.CASCADE)
    quantity = models.CharField(max_length=50, blank=True)
    expiry = models.DateField(null=True, blank=True)
    objects = ProjectSampleQueryset.as_manager()

    class Meta:
        unique_together = ('material', 'sample')

    def __str__(self):
        return "{0} ({1})".format(self.sample.name, self.quantity)

    def full_state(self):
        if self.expiry and self.state == self.STATES.approved and self.expiry <= timezone.now().date():
            return self.STATES.expired
        else:
            return self.state


class BeamTime(Event):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="beamtimes", null=True)
    beamline = models.ForeignKey('beamlines.Facility', on_delete=models.CASCADE, related_name="beamtimes")
    tags = models.ManyToManyField('beamlines.FacilityTag', related_name='beamtimes', blank=True)
    objects = EventQuerySet.as_manager()

    def __str__(self):
        return "{}-{}".format(self.start, self.end)

    def sessions(self):
        return Session.objects.filter(project=self.project, beamline=self.beamline).within(self)

    def principal_investigator(self):
        return self.project.get_leader()

    principal_investigator.sort_field = 'project__leader'

    class Meta:
        unique_together = [('project', 'beamline', 'start')]


class Reservation(TimeStampedModel):
    TYPES = PROJECT_TYPES
    cycle = models.ForeignKey('proposals.ReviewCycle', on_delete=models.CASCADE, related_name="reservations")
    beamline = models.ForeignKey('beamlines.Facility', on_delete=models.CASCADE, related_name="reservations")
    shifts = models.PositiveIntegerField(default=0)
    kind = models.CharField(max_length=20, choices=TYPES, null=True)
    comments = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('beamline', 'cycle', 'kind')
