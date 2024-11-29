import calendar
import functools
import itertools
from datetime import timedelta

from dateutil import parser
from django.conf import settings
from django.contrib import messages
from django.db.models import Q, Sum, Case, When, IntegerField, Value, F
from django.db.models.functions import Coalesce
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import detail, edit, View, TemplateView
from itemlist.views import ItemListView
from rest_framework import generics, permissions
from rest_framework.parsers import JSONParser

from beamlines.filters import BeamlineFilterFactory
from beamlines.models import Facility
from dynforms.models import FormType
from misc.filters import FutureDateListFilterFactory
from misc.functions import Shifts
from misc.models import ActivityLog
from misc.views import ConfirmDetailView, ClarificationResponse, RequestClarification
from notifier import notify
from proposals.filters import CycleFilterFactory
from proposals.models import ReviewCycle
from proposals.utils import truncated_title
from roleperms.views import RolePermsViewMixin
from samples.models import Sample
from samples.templatetags.samples_tags import pictogram_url
from scheduler.utils import round_time
from scheduler.views import EventEditor, EventUpdateAPI, EventStatsAPI
from users.models import User
from . import forms
from . import models
from . import serializers
from . import utils


def _fmt_beamlines(bls, obj=None):
    return ', '.join([bl.acronym for bl in bls.distinct()])


def _fmt_project_state(state, obj=None):
    if state == 'active':
        return '<i title="Active" class="bi-check2-square text-success-light icon-fw"></i> Active'
    elif state == 'pending':
        return '<i title="Pending" class="bi-hourglass text-info icon-fw"></i> Pending'
    else:
        return '<i title="Inactive" class="bi-exclamation-triangle text-danger icon-fw"></i> Inactive'


def _fmt_pictograms(pictograms, obj=None):
    txt = ''
    for pic in pictograms:
        url = pictogram_url(pic)
        txt += f'<img class="media-object pull-left" width="20" height="20" src="{url}" title="{pic.name}">'
    return txt


def _fmt_localtime(datetime, obj=None):
    return timezone.localtime(datetime).strftime('%Y-%m-%d %H:%M')


def _fmt_full_name(user, obj=None):
    return user.get_full_name()


class ProjectList(RolePermsViewMixin, ItemListView):
    model = models.Project
    template_name = "item-list.html"
    paginate_by = 50
    list_columns = ['code', 'title', 'spokesperson', 'end_date', 'kind', 'facility_codes', 'state']
    list_filters = ['start_date', 'end_date', FutureDateListFilterFactory.new('end_date'), CycleFilterFactory.new('cycle'),
                    'kind',
                    BeamlineFilterFactory.new("beamlines")]
    list_search = ['proposal__title', 'proposal__team', 'proposal__keywords', 'id']
    list_styles = {'title': 'col-xs-3', 'state': 'text-center'}
    list_transforms = {'state': _fmt_project_state, 'title': truncated_title}
    link_url = "project-detail"
    order_by = ['end_date', 'cycle', '-created']
    admin_roles = ['administrator:uso']
    allowed_roles = ['employee:hse', 'administrator:uso']


class MaterialList(RolePermsViewMixin, ItemListView):
    model = models.Material
    template_name = "item-list.html"
    paginate_by = 15
    list_columns = ['code', 'project', 'title', 'state', 'risk_level', 'pictograms']
    list_filters = ['created', 'modified', 'state', 'risk_level']
    list_transforms = {'pictograms': _fmt_pictograms}
    list_search = ['project__title', 'project__spokesperson__username', 'project__id',
                   'project__spokesperson__last_name',
                   'project__spokesperson__first_name', 'id']
    list_styles = {'title': 'col-xs-6'}
    link_url = "material-detail"
    order_by = ['-modified', 'state']
    list_title = 'Materials'
    admin_roles = ['administrator:uso']
    allowed_roles = ['employee:hse', 'administrator:uso']


class SessionList(RolePermsViewMixin, ItemListView):
    queryset = models.Session.objects.with_shifts()
    template_name = "item-list.html"
    paginate_by = 15
    list_columns = ['project', 'beamline', 'state', 'kind', 'spokesperson', 'start', 'shifts']
    list_filters = ['modified', BeamlineFilterFactory.new("beamline"), 'state', 'kind']
    list_search = ['project__title', 'project__spokesperson__username', 'project__id',
                   'project__spokesperson__last_name',
                   'project__spokesperson__first_name', 'id']
    list_transforms = {'start': _fmt_localtime}
    link_url = "session-detail"
    order_by = ['-modified', 'state']
    admin_roles = ['administrator:uso']
    allowed_roles = ['employee:hse', 'administrator:uso']


class LabSessionList(RolePermsViewMixin, ItemListView):
    queryset = models.LabSession.objects.all()
    template_name = "item-list.html"
    paginate_by = 15
    list_columns = ['project', 'lab', 'state', 'spokesperson', 'start', 'end']
    list_filters = ['modified']
    list_search = ['project__title', 'project__spokesperson__username', 'project__id',
                   'project__spokesperson__last_name',
                   'project__spokesperson__first_name', 'id']
    list_transforms = {'start': _fmt_localtime, 'end': _fmt_localtime}
    link_url = "lab-permit"
    order_by = ['-modified']
    admin_roles = ['administrator:uso']
    allowed_roles = ['employee:hse', 'administrator:uso']


class UserProjectList(RolePermsViewMixin, ItemListView):
    model = models.Project
    template_name = "item-list.html"
    paginate_by = 50
    list_columns = ['code', 'title', 'spokesperson', 'end_date', 'kind', 'facility_codes', 'state']
    list_filters = ['start_date', 'end_date', CycleFilterFactory.new('cycle'), 'kind', BeamlineFilterFactory.new("beamlines")]
    list_search = ['id', 'proposal__title', 'proposal__team', 'proposal__keywords']
    list_styles = {'title': 'col-xs-3', 'state': 'text-center'}
    list_transforms = {'state': _fmt_project_state, 'title': truncated_title}
    link_url = "project-detail"
    order_by = ['-end_date', '-created']
    list_title = 'My Projects'
    admin_roles = ['administrator:uso']

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.request.user.projects.all()
        return super().get_queryset(*args, **kwargs)


class UserBeamTimeList(RolePermsViewMixin, ItemListView):
    model = models.BeamTime
    template_name = "item-list.html"
    paginate_by = 25
    list_columns = ['project', 'principal_investigator', 'beamline', 'start', 'end']
    list_filters = [BeamlineFilterFactory.new("beamline")]
    list_search = ['id', 'project__proposal__title', 'project__team__last_name', 'beamline__acronym']
    list_transforms = {'start': _fmt_localtime, 'end': _fmt_localtime}
    order_by = ['-end', '-created']

    list_title = 'My Beamtime'
    admin_roles = ['administrator:uso']

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.model.objects.filter(project__team=self.request.user)
        return super().get_queryset(*args, **kwargs)

    def get_link_url(self, obj):
        return reverse('project-detail', kwargs={'pk': obj.project.pk})


class BeamlineProjectList(RolePermsViewMixin, ItemListView):
    model = models.Project
    template_name = "item-list.html"
    paginate_by = 50
    list_columns = ['code', 'title', 'spokesperson', 'end_date', 'kind', 'state']
    list_filters = ['start_date', 'end_date', CycleFilterFactory.new('cycle'), 'kind', BeamlineFilterFactory.new("beamlines")]
    list_search = ['id', 'proposal__title', 'proposal__team', 'proposal__keywords']
    list_styles = {'title': 'col-xs-3'}
    list_transforms = {'beamlines': _fmt_beamlines, 'state': _fmt_project_state, 'title': truncated_title}
    link_url = "project-detail"
    order_by = ['-cycle__start_date', '-created']
    list_title = 'Projects'
    admin_roles = ['administrator:uso']
    allowed_roles = ['administrator:uso']

    def get_list_title(self):
        if self.kwargs.get('cycle'):
            cycle = models.ReviewCycle.objects.get(pk=self.kwargs['cycle'])
            return '{} Projects: {}'.format(self.facility.acronym, cycle)
        else:
            return '{} Projects'.format(self.facility.acronym)

    def check_allowed(self):
        self.facility = Facility.objects.get(pk=self.kwargs['fac'])
        allowed = super().check_allowed() or self.facility.is_staff(self.request.user)
        return allowed

    def get_queryset(self, *args, **kwargs):
        self.queryset = models.Project.objects.filter(
            Q(allocations__beamline=self.facility) | Q(allocations__beamline__parent=self.facility)
        ).distinct()
        if self.kwargs.get('cycle'):
            self.queryset.filter(allocations__cycle=self.kwargs['cycle']).distinct()
        return super().get_queryset(*args, **kwargs)


class ProjectDetail(RolePermsViewMixin, detail.DetailView):
    template_name = "projects/project-detail.html"
    model = models.Project
    allowed_roles = ['administrator:uso', 'employee:hse']
    admin_roles = ['administrator:uso']

    def check_allowed(self):
        project = self.get_object()
        user = self.request.user
        allowed = (super().check_allowed() or self.check_admin() or project.team.filter(
            username=user.username
        ).exists() or any(
            fac.is_staff(user) for fac in project.beamlines.all()
        ))
        return allowed

    def check_admin(self):
        project = self.get_object()
        user = self.request.user
        return super().check_admin() or any(fac.is_staff(user) for fac in project.beamlines.all())

    def check_owner(self, obj):
        return self.request.user in [obj.spokesperson, obj.leader, obj.delegate]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['training_url'] = settings.TRAINING_SERVER
        return context


class ProjectHistory(RolePermsViewMixin, ItemListView):
    model = models.Session
    template_name = "item-list.html"
    paginate_by = 15
    list_columns = ['project', 'beamline__acronym', 'state', 'kind', 'spokesperson', 'start', 'shifts']
    list_filters = ['created', 'modified', 'state', 'kind']
    list_search = ['project__title', 'project__spokesperson__username', 'project__id',
                   'project__spokesperson__last_name',
                   'project__spokesperson__first_name', 'id']
    list_transforms = {'start': _fmt_localtime}
    link_url = "session-detail"
    order_by = ['-modified', 'state']
    admin_roles = ['administrator:uso']
    allowed_roles = ['employee:hse', 'administrator:uso']

    def get_list_title(self):
        return "{} Session History".format(self.project)

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.project.sessions.filter().with_shifts()
        return super().get_queryset(*args, **kwargs)

    def check_owner(self, obj):
        return self.request.user in [obj.spokesperson, obj.leader, obj.delegate]

    def check_allowed(self):
        self.project = models.Project.objects.get(pk=self.kwargs['pk'])
        allowed = (super().check_allowed() or self.check_admin() or self.project.team.filter(
            username=self.request.user.username
        ).exists() or any(
            fac.is_staff(self.request.user) for fac in self.project.beamlines.all()
        ))
        return allowed


class AllocRequestList(RolePermsViewMixin, ItemListView):
    model = models.AllocationRequest
    template_name = "item-list.html"
    paginate_by = 15
    list_columns = ['project', 'created', 'beamline', 'shift_request', 'state']
    list_filters = ['created', 'modified', 'state', 'beamline']
    list_search = ['project__title', 'project__spokesperson__username', 'project__id',
                   'project__spokesperson__last_name',
                   'project__spokesperson__first_name', 'id']
    order_by = ['-modified', 'state']
    list_title = 'Allocation Requests'
    admin_roles = ['administrator:uso']
    allowed_roles = ['administrator:uso']


class ShiftRequestList(RolePermsViewMixin, ItemListView):
    model = models.ShiftRequest
    template_name = "item-list.html"
    paginate_by = 15
    list_columns = ['allocation__project', 'created', 'allocation__beamline', 'shift_request', 'state']
    list_filters = ['created', 'modified', 'state']
    list_search = ['project__title', 'project__spokesperson__username', 'project__id',
                   'project__spokesperson__last_name',
                   'project__spokesperson__first_name', 'id']
    order_by = ['-modified', 'state']
    list_title = 'Shift Requests'
    admin_roles = ['administrator:uso']
    allowed_roles = ['administrator:uso']

    def get_list_title(self):
        return '{} Shift Requests: {}'.format(self.facility.acronym, self.cycle)

    def check_allowed(self):
        self.facility = Facility.objects.get(pk=self.kwargs['pk'])
        self.cycle = ReviewCycle.objects.get(pk=self.kwargs['cycle'])
        allowed = super().check_allowed() or self.facility.is_admin(self.request.user)
        return allowed

    def get_queryset(self, *args, **kwargs):
        self.queryset = models.ShiftRequest.objects.filter(allocation__beamline=self.kwargs['pk'])
        return super().get_queryset(*args, **kwargs)


class MaterialDetail(RolePermsViewMixin, detail.DetailView):
    template_name = "projects/material-detail.html"
    model = models.Material
    allowed_roles = ['administrator:uso', 'employee:hse']
    admin_roles = ['administrator:uso']

    def check_owner(self, obj):
        return obj.is_owned_by(self.request.user)

    def check_allowed(self):
        material = self.get_object()
        allowed = (super().check_allowed() or self.check_admin() or self.check_owner(material) or any(
            fac.is_staff(self.request.user) for fac in material.project.beamlines.all()
        ))
        return allowed


class CreateProject(RolePermsViewMixin, edit.CreateView):
    form_class = forms.ProjectForm
    model = models.Project
    template_name = "projects/forms/project_form.html"
    allowed_roles = ['administrator:uso']

    def get_initial(self):
        initial = super().get_initial()
        initial['spokesperson'] = self.request.user
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = "Create Purchased Access Project"
        return context

    def get_success_url(self):
        success_url = reverse("project-list")
        return success_url

    def form_valid(self, form):
        info = form.cleaned_data
        info['kind'] = 'purchased'
        info['spokesperson'] = self.request.user
        self.object = self.model.objects.create(**info)
        project = self.object
        project.refresh_team()
        messages.add_message(self.request, messages.SUCCESS, 'Project was created successfully')

        # team and allocations
        for bl in info['details'].get('beamline_reqs', []):
            utils.create_project_allocations(self.object, bl, self.object.cycle)

        # create materials
        material = models.Material.objects.get_or_create(project=project)
        to_create = [models.ProjectSample(material=material, sample_id=sample['sample'], quantity=sample['quantity'])
                     for sample in
                     info['details'].get('sample_list', [])]
        models.ProjectSample.objects.bulk_create(to_create)
        hazards = material.samples.values_list('sample__hazards__pk', flat=True).distinct()
        material.hazards.add(*hazards)
        material.hazards.add(*info['details'].get('sample_hazards', []))
        models.Material.objects.filter(pk=material.pk).update(
            procedure=info['details'].get('sample_handling', ''), waste=info['details'].get('waste_generation', []),
            disposal=info['details'].get('disposal_procedure', ''), equipment=info['details'].get('equipment', []), )

        # Create Material Reviews
        if material.needs_ethics():
            ethics = models.Review.objects.create(
                reference=material, kind="ethics", role="ethics-reviewer",
                spec_id=FormType.objects.get(code="ethics_review").spec.pk
            )

        return HttpResponseRedirect(self.get_success_url())


class SessionDetail(RolePermsViewMixin, detail.DetailView):
    template_name = "projects/session-detail.html"
    model = models.Session
    allowed_roles = ['administrator:uso', 'employee:hse']
    admin_roles = ['administrator:uso']
    terminate_roles = ['employee:hse']

    def check_owner(self, obj):
        obj.is_owned_by(self.request.user)

    def check_allowed(self):
        session = self.get_object()
        allowed = (super().check_allowed() or self.check_owner(session) or session.beamline.is_staff(self.request.user))
        return allowed

    def check_admin(self):
        session = self.get_object()
        admin = super().check_admin() or session.beamline.is_staff(self.request.user)
        return admin

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['beamlines'] = [self.object.beamline]
        context['samples'] = [(s.sample, s.quantity) for s in self.object.samples.all()]
        context['can_terminate'] = self.request.user.has_roles(self.terminate_roles)
        return context


class LabPermit(RolePermsViewMixin, detail.DetailView):
    template_name = "projects/lab_permit.html"
    model = models.LabSession
    admin_roles = ['administrator:uso']

    def check_owner(self, obj):
        return obj.is_owned_by(self.request.user)


class SessionHandOver(RolePermsViewMixin, edit.CreateView):
    model = models.Session
    form_class = forms.HandOverForm
    template_name = "forms/modal.html"
    allowed_roles = ['administrator:uso']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['project'] = self.project
        kwargs['facility'] = self.facility
        return kwargs

    def check_allowed(self):
        self.facility = Facility.objects.get(acronym=self.kwargs['fac'])
        allowed = super().check_allowed() or self.facility.is_staff(self.request.user)
        return allowed

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['facility'] = self.facility
        context['project'] = self.project
        context['tags'] = self.project.tags.all() if not self.beamtime else self.beamtime.tags.all()
        return context

    def get_initial(self):
        initial = super().get_initial()

        start = timezone.now()
        limit = timezone.now() + timedelta(days=4)
        self.project = models.Project.objects.get(pk=self.kwargs['pk'])
        self.beamtime = self.project.beamtimes.filter(start__gte=start, end__lte=limit, beamline=self.facility).first()

        one_shift = timedelta(hours=self.facility.shift_size)
        now = round_time(timezone.localtime(timezone.now()) + one_shift, one_shift)
        initial['start'] = now if not self.beamtime else self.beamtime.start
        alt_end = now + one_shift
        initial['end'] = alt_end if not self.beamtime else self.beamtime.end

        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        data['beamline'] = self.facility
        data['project'] = self.project
        data['staff'] = self.request.user

        sessions = models.Session.objects.filter(project=self.project, beamline=self.facility)
        existing = sessions.within(data) | sessions.encloses(data) | sessions.intersects(data)

        if existing.exists():
            messages.error(self.request, 'HandOver failed. Existing Sessions exist within time period!')
        else:
            models.Session.objects.create(**data)
            messages.success(self.request, 'Beamline hand-over successful')
        return JsonResponse(
            {
                "url": "",
            }
        )


class SessionExtend(RolePermsViewMixin, edit.UpdateView):
    model = models.Session
    template_name = "forms/modal.html"
    form_class = forms.ExtensionForm
    allowed_roles = ['administrator:uso']

    def check_allowed(self):
        self.session = self.get_object()
        facility = self.session.beamline

        allowed = super().check_allowed() or facility.is_staff(self.request.user)
        return allowed

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['session'] = self.session
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['session'] = self.session
        return context

    def form_valid(self, form):
        session = self.get_object()
        shifts = form.cleaned_data['shifts']
        end = session.end + timedelta(hours=8 * shifts)
        session.log('Session extended for {} shift(s) by {} on {}'.format(shifts, self.request.user, timezone.now()))
        models.Session.objects.filter(pk=session.pk).update(
            details=session.details, end=(session.end + timedelta(hours=8 * shifts))
        )
        messages.success(self.request, 'Session extended by {} shifts until {}'.format(shifts, session.end))
        return JsonResponse(
            {
                "url": "",
            }
        )


class SessionSignOn(RolePermsViewMixin, edit.UpdateView):
    form_class = forms.SessionForm
    template_name = "forms/modal.html"
    model = models.Session
    allowed_roles = ['administrator:uso']
    admin_roles = ['administrator:uso']

    def check_allowed(self):
        self.session = self.get_object()
        self.facility = self.session.beamline
        allowed = (super().check_allowed() or self.check_owner(self.session) or self.facility.is_staff(
            self.request.user
        ))
        return allowed

    def check_owner(self, obj):
        return obj.is_owned_by(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['facility'] = self.facility
        context['project'] = self.session.project
        context['session'] = self.session
        context['material'] = self.session.project.materials.approved().last()
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_success_url(self):
        success_url = reverse("session-detail", kwargs={'pk': self.object.pk})
        return success_url

    def get_initial(self):
        initial = super().get_initial()
        initial['user'] = self.request.user
        initial['project'] = self.get_object().project
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        session = self.get_object()

        # check changes
        logs = session.details.get('history', [])
        now = timezone.localtime(timezone.now())

        old_samples = set(session.samples.all())
        old_team = set(session.team.all())
        new_samples = set(data.get('samples', []))
        new_team = set(data.get('team', []))

        changes = {
            'Removed': {
                'samples': old_samples - new_samples, 'team': old_team - new_team
            }, 'Added': {
                'samples': new_samples - old_samples, 'team': new_team - old_team
            }
        }
        activities = ['Sign-On updated by {} on {}'.format(self.request.user, now.strftime('%c'))]
        for action, subjects in list(changes.items()):
            for object_type, objects in list(subjects.items()):
                if objects:
                    activities.append(
                        '{} {}: {};'.format(
                            action, object_type, ", ".join(["'{}'".format(x) for x in objects])
                        )
                    )
        session.log("; ".join(activities))

        session.samples.clear()
        session.samples.add(*data.get('samples', []))
        session.team.clear()
        session.team.add(*data.get('team', []))
        session.details.update(history=logs)

        models.Session.objects.filter(pk=session.pk).update(
            spokesperson=self.request.user, state=session.STATES.live, details=session.details
        )
        messages.add_message(self.request, messages.SUCCESS, 'Beamtime signed on successfully')

        # sign-off previous users on beamline if any
        for old_session in session.beamline.sessions.filter(state=session.STATES.live).exclude(pk=session.pk):
            bl_role = "beamline-admin:{}".format(old_session.beamline.acronym.lower())
            recipients = [bl_role]
            for u in {old_session.staff, old_session.spokesperson}:
                if not u.has_role(bl_role):
                    recipients.append(u)
            reason = "Another user has taken control of the beamline"
            notify.send(
                recipients, 'auto-sign-off', level=notify.LEVELS.important, context={
                    'session': old_session, 'reason': reason
                }
            )
            old_session.log(
                'Auto Sign-Off on {}, New user on beamline.'.format(now.strftime('%c'))
            )
            old_session.state = session.STATES.complete
            old_session.save()

        # cancel outstanding sessions on this beamline
        for old_session in session.beamline.sessions.filter(state=session.STATES.ready, start__lt=now):
            old_session.log('Cancelled on {}, Users did not sign-on as expected'.format(now.strftime('%c')))
            old_session.state = session.STATES.cancelled
            old_session.save()

        return JsonResponse(
            {
                'url': self.get_success_url()
            }
        )


class SessionSignOff(RolePermsViewMixin, ConfirmDetailView):
    model = models.Session
    template_name = "projects/forms/signoff.html"
    allowed_roles = ['administrator:uso']

    def check_allowed(self):
        self.session = self.get_object()
        self.project = self.session.project
        self.facility = self.session.beamline

        allowed = (super().check_allowed() or self.check_owner(self.session) or self.facility.is_staff(
            self.request.user
        ))
        return allowed

    def check_owner(self, obj):
        return obj.is_owned_by(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['facility'] = self.facility
        context['project'] = self.project
        return context

    def confirmed(self, *args, **kwargs):
        log = self.session.details.get('history', [])
        now = timezone.localtime(timezone.now())
        log.append('SignOff by {} on {}'.format(self.request.user, now.strftime('%c')))
        self.session.details.update(history=log)
        models.Session.objects.filter(pk=self.session.pk).update(
            state=self.session.STATES.complete, details=self.session.details
        )
        messages.success(self.request, 'Beamline Sign-Off successful')
        return JsonResponse(
            {
                "url": "",
            }
        )


class TerminateSession(RolePermsViewMixin, edit.CreateView):
    model = models.Session
    form_class = forms.TerminationForm
    template_name = "forms/modal.html"
    allowed_roles = ["administrator:uso", "employee:hse"]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def check_allowed(self):
        self.session = self.get_object()
        self.facility = self.session.beamline
        allowed = super().check_allowed() or self.facility.is_admin(self.request.user)
        return allowed

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['session'] = self.session
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        session = self.get_object()

        models.Session.objects.filter(pk=session.pk).update(state=models.Session.STATES.terminated)
        msg = 'Session Terminated by {} on {} because: "{}"'.format(
            self.request.user, timezone.localtime(timezone.now()), data['reason']
        )
        session.log(msg)
        ActivityLog.objects.log(
            self.request, session, kind=ActivityLog.TYPES.modify,
            description="Session Terminated because: {}".format(data['reason'])
        )
        messages.success(self.request, 'Session terminated!')

        # Notify relevant parties
        bl_role = "beamline-admin:{}".format(session.beamline.acronym.lower())
        recipients = [bl_role]
        for u in [_f for _f in {session.staff, session.spokesperson} if _f]:
            if not u.has_role(bl_role):
                recipients.append(u)
        notify.send(
            recipients, 'session-terminated', level=notify.LEVELS.important, context={
                'session': session, 'reason': data['reason'], 'terminator': self.request.user,
            }
        )

        return JsonResponse(
            {
                "url": "",
            }
        )


class LabSignOn(RolePermsViewMixin, edit.CreateView):
    model = models.LabSession
    form_class = forms.LabSessionForm
    template_name = "forms/modal.html"
    allowed_roles = ["administrator:uso"]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['project'] = self.project
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        initial['start'] = round_time(timezone.localtime(timezone.now()), timedelta(minutes=30))
        initial['end'] = round_time(timezone.localtime(timezone.now()) + timedelta(hours=4), timedelta(hours=4))
        return initial

    def check_allowed(self):
        self.project = models.Project.objects.get(pk=self.kwargs['pk'])
        allowed = super().check_allowed() or self.check_owner(self.project)
        return allowed

    def check_owner(self, obj):
        return obj.is_owned_by(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['project'] = self.project
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        data['project'] = self.project
        data['spokesperson'] = self.request.user

        sessions = models.LabSession.objects.filter(project=self.project, lab=data['lab'])
        existing = sessions.within(data) | sessions.encloses(data) | sessions.intersects(data)

        if existing.exists():
            messages.error(self.request, 'Lab Sign-On failed. You have other sessions within the requested period!')
        else:
            team = data.pop('team')
            equipment = data.pop('equipment')
            workspaces = data.pop('workspaces').filter(lab=data['lab'])
            session = models.LabSession.objects.create(**data)
            session.team.add(*team)
            session.workspaces.add(*workspaces)
            session.equipment.add(*equipment)
            messages.success(self.request, 'Lab Sign-On successful')
        return JsonResponse(
            {
                "url": "",
            }
        )


class LabSignOff(RolePermsViewMixin, ConfirmDetailView):
    model = models.LabSession
    template_name = "projects/forms/signoff.html"
    allowed_roles = ['administrator:uso', 'floor-coordinator']

    def check_allowed(self):
        self.session = self.get_object()
        self.project = self.session.project
        self.lab = self.session.lab
        allowed = (
            super().check_allowed() or self.check_owner(self.session) or self.session.team.filter(
                username=self.request.user.username
            ).exists())
        return allowed

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['facility'] = self.lab
        context['project'] = self.project
        return context

    def confirmed(self, *args, **kwargs):
        log = self.session.details.get('history', [])
        now = timezone.localtime(timezone.now())
        log.append('SignOff by {} on {}'.format(self.request.user, now.strftime('%c')))
        self.session.details.update(history=log)
        models.LabSession.objects.filter(pk=self.session.pk).update(details=self.session.details, end=now)
        messages.success(self.request, 'Lab Sign-Off successful')
        return JsonResponse(
            {
                "url": "",
            }
        )


class CancelLabSession(RolePermsViewMixin, ConfirmDetailView):
    model = models.LabSession
    template_name = "forms/delete.html"
    allowed_roles = ['administrator:uso']
    admin_roles = ['administrator:uso']

    def check_allowed(self):
        session = self.get_object()
        return (session.state() == models.LabSession.STATES.pending and (
                super().check_allowed() or session.team.filter(username=self.request.user.username).exists()))

    def confirmed(self, *args, **kwargs):
        obj = self.get_object()
        project = obj.project
        obj.delete()
        messages.info(self.request, "Permit cancelled!")
        return JsonResponse(
            {
                "url": reverse('project-detail', kwargs={'pk': project.pk})
            }
        )


class UpdateMaterial(RolePermsViewMixin, edit.FormView):
    form_class = forms.MaterialForm
    allowed_roles = ['administrator:uso']
    admin_roles = ['administrator:uso']
    template_name = "projects/forms/project_form.html"

    def get_object(self):
        self.project = models.Project.objects.get(pk=self.kwargs['pk'])
        material = self.project.materials.pending().last()
        self.object = self.project.materials.approved().last() if not material else material
        return self.object

    def check_allowed(self):
        material = self.get_object()
        allowed = super().check_allowed() or self.check_owner(material.project)
        return allowed

    def check_owner(self, obj):
        return obj.is_owned_by(self.request.user)

    def get_success_url(self):
        success_url = reverse("project-detail", kwargs={'pk': self.kwargs['pk']})
        return success_url

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = "Amend Materials"
        return context

    def get_initial(self):
        initial = super().get_initial()
        self.get_object()
        if self.object:
            initial.update(
                {
                    'sample_list': self.object.sample_list(), 'sample_handling': self.object.procedure,
                    'waste_generation': self.object.waste,
                    'disposal_procedure': self.object.disposal, 'equipment': self.object.equipment,
                }
            )
        return initial

    def form_valid(self, form):
        info = form.cleaned_data['details']
        obj = self.object

        # FIXME: Check if any review has started

        if obj.state != obj.STATES.pending:
            obj.pk = None
            obj.state = obj.STATES.pending
            obj.save()

        safety_required = any(
            [obj.procedure == info.get('sample_handling', ''), obj.waste == info.get('waste_generation', []),
             obj.disposal == info.get('disposal_procedure', ''), obj.equipment == info.get('equipment', []), ]
        )
        obj.procedure = info.get('sample_handling', '')
        obj.waste = info.get('waste_generation', [])
        obj.disposal = info.get('disposal_procedure', '')
        obj.equipment = info.get('equipment', [])
        obj.save()

        for s in info.get('sample_list', []):
            sample = Sample.objects.get(pk=s['sample'])
            ps, created = models.ProjectSample.objects.get_or_create(
                material=obj, sample=sample, quantity=s['quantity']
            )
            if created:
                safety_required = True

        if safety_required:
            # Create Material Reviews
            cycle = self.project.allocations.last().cycle
            approval, created = obj.reviews.get_or_create(
                kind='approval', spec=FormType.objects.get(code="safety_approval").spec, defaults={
                    'cycle': cycle, 'state': models.Review.STATES.open, 'role': "safety-approver"
                }
            )
            if obj.needs_ethics():
                ethics, created = obj.reviews.get_or_create(
                    kind="ethics", spec=FormType.objects.get(code="ethics_review").spec, defaults={
                        'cycle': cycle, 'state': models.Review.STATES.open, 'role': "ethics-approver"
                    }
                )

        # check if project has been scheduled then update due date
        obj.update_due_dates()

        messages.add_message(self.request, messages.SUCCESS, 'Materials amendment was submitted successfully')
        return HttpResponseRedirect(self.get_success_url())


class UpdateTeam(RolePermsViewMixin, edit.UpdateView):
    form_class = forms.TeamForm
    model = models.Project
    template_name = "projects/forms/project_form.html"
    allowed_roles = ['administrator:uso']
    admin_roles = ['administrator:uso']

    def check_allowed(self):
        self.project = self.get_object()
        return super().check_allowed() or self.check_owner(self.project)

    def check_owner(self, obj):
        return obj.is_owned_by(self.request.user)

    def get_initial(self):
        initial = super().get_initial()
        initial.update(
            {
                'team_members': self.project.team_members(), 'leader': self.project.get_leader(),
                'delegate': self.project.get_delegate(),
                'invoice_address': self.project.invoice_address(), 'invoice_email': self.project.invoice_email()
            }
        )
        return initial

    def get_success_url(self):
        success_url = reverse("project-detail", kwargs={'pk': self.object.pk})
        return success_url

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = "Update Research Team Members"
        return context

    def form_valid(self, form):
        data = form.cleaned_data['details']
        for f in ['invoice_address', 'invoice_email', 'leader', 'delegate']:
            self.object.details[f] = data.get(f)
        self.object.details['team_members'] = data.get('team_members', [])

        self.object.save()
        self.object.refresh_team()

        messages.add_message(self.request, messages.SUCCESS, 'Project was updated successfully')
        return HttpResponseRedirect(self.get_success_url())


class RefreshTeam(RolePermsViewMixin, detail.View):
    model = models.Project
    allowed_roles = ['administrator:uso']
    admin_roles = ['administrator:uso']

    def check_allowed(self):
        self.project = models.Project.objects.get(pk=self.kwargs['pk'])
        return (
            super().check_allowed() or self.check_owner(self.project) or any(
                fac.is_staff(self.request.user) for fac in self.project.beamlines.all()
            ))

    def check_owner(self, obj):
        return obj.is_owned_by(self.request.user)

    def get(self, *args, **kwargs):
        self.project.refresh_team()
        return HttpResponseRedirect(reverse('project-detail', kwargs={'pk': self.project.pk}))


class AllocDecider(object):
    def __init__(self, total, extra=0):
        self.decision = 0
        self.cutoff = 0
        self.total = total
        self.extra = extra
        self.used = 0

    def __call__(self, a1, a2):
        if isinstance(a1, AllocDecider):
            self.used = self.used + a2.shift_request
        else:
            self.used = a1.shift_request + a2.shift_request
        if self.used <= self.total:
            self.cutoff = max(a2.score_merit, self.cutoff)
        if self.used <= (self.total + self.extra):
            self.decision = max(a2.score_merit, self.decision)
        return self

    def __str__(self):
        return '{} [{}:{}]'.format(self.used, self.cutoff, self.decision)


class AllocateBeamtime(RolePermsViewMixin, TemplateView):
    template_name = "projects/allocate.html"
    allowed_roles = ['administrator:uso']
    admin_roles = ['administrator:uso']

    def check_allowed(self):
        self.facility = Facility.objects.filter(acronym__iexact=self.kwargs['fac']).first()
        return super().check_allowed() or self.facility.is_admin(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cycle = ReviewCycle.objects.get(pk=self.kwargs.get('pk'))
        fac = self.facility
        schedule = cycle.schedule
        reservations = models.Reservation.objects.filter(beamline=fac, cycle=cycle)
        allocations = cycle.allocations.filter(beamline=fac)

        total = schedule.normal_shifts()
        unavailable = reservations.filter(kind__in=['', None]).aggregate(total=Coalesce(Sum('shifts'), 0))

        fac_total = total - unavailable['total']
        context['facility'] = fac
        context['cycle'] = cycle
        context['discretionary'] = 0
        context['total_shifts'] = total
        context['available_shifts'] = fac_total
        context['unavailable_shifts'] = unavailable['total']
        left_over = fac_total
        pools = {}
        for pool_type in models.PROJECT_TYPES:
            pool = pool_type[0]
            percent = fac.details.get('beamtime', {}).get(pool) or 0
            reserved = reservations.filter(kind=pool).aggregate(total=Coalesce(Sum('shifts'), 0))
            pool_allocations = allocations.filter(project__kind=pool).annotate(
                priority=Case(
                    When(score_merit=0, then=Value('1')), default=Value('0'), output_field=IntegerField(), )
            )

            used = pool_allocations.aggregate(total=Coalesce(Sum('shifts'), 0))
            available = int(fac_total * percent / 100.0)
            left_over -= available
            unused = available - (used['total'] + reserved['total'])

            if pool != 'user':
                context['discretionary'] += unused
            info = {
                'shifts': available, 'name': models.PROJECT_TYPES[pool], 'key': pool, 'decision': 0, 'percent': percent,
                'reserved': reserved,
                'used': used, 'unused': unused, 'projects': pool_allocations.order_by(
                    'priority', 'score_merit', 'score_suitability', 'score_capability', 'score_technical'
                ).distinct(),
            }
            pools[pool] = info

        context['discretionary'] += left_over
        if pools.get('user', {}).get('projects', models.Project.objects.none()).count() > 1:
            decider = AllocDecider(pools['user']['shifts'], extra=context['discretionary'])
            final = functools.reduce(decider, pools['user']['projects'])
            pools['user']['decision'] = final.decision
            pools['user']['cutoff'] = final.cutoff
            pools['user']['available'] = pools['user']['shifts'] + context['discretionary']
        context['pools'] = pools

        return context


class EditAllocation(RolePermsViewMixin, edit.UpdateView):
    form_class = forms.AllocationForm
    model = models.Allocation
    template_name = "forms/modal.html"
    allowed_roles = ['administrator:uso']
    admin_roles = ['administrator:uso']

    def check_allowed(self):
        alloc = self.get_object()
        return super().check_allowed() or alloc.beamline.is_admin(self.request.user)

    def get_success_url(self):
        return reverse(
            'allocate-review-cycle', kwargs={'pk': self.object.cycle.pk, 'fac': self.object.beamline.acronym}
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_initial(self):
        self.initial = super().get_initial()
        self.initial.update(
            {
                "last_cycle": ReviewCycle.objects.filter(end_date=self.get_object().project.end_date).last()
            }
        )
        return self.initial

    def form_valid(self, form):
        super().form_valid(form)
        data = form.cleaned_data
        alloc = self.get_object()
        if 'last_cycle' in form.changed_data:
            models.Project.objects.filter(pk=alloc.project.pk).update(end_date=data['last_cycle'].end_date)
            models.Allocation.objects.filter(
                project=alloc.project, beamline=alloc.beamline, cycle__end_date__gt=data['last_cycle'].end_date
            ).delete()
        return JsonResponse(
            {
                "url": ""
            }
        )


class EditReservation(RolePermsViewMixin, edit.CreateView):
    form_class = forms.ReservationForm
    model = models.Reservation
    template_name = "forms/modal.html"
    allowed_roles = ['administrator:uso']
    admin_roles = ['administrator:uso']

    def check_allowed(self):
        fac = Facility.objects.get(acronym__iexact=self.kwargs['fac'])
        return super().check_allowed() or fac.is_admin(self.request.user)

    def get_success_url(self):
        return reverse('allocate-review-cycle', kwargs={'pk': self.kwargs['cycle'], 'fac': self.kwargs['fac']})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        res = models.Reservation.objects.filter(
            beamline__acronym=self.kwargs['fac'], cycle__pk=self.kwargs['cycle'], kind=self.kwargs.get('pool', None)
        ).first()
        if res:
            initial.update(
                {
                    'comments': res.comments, 'shifts': res.shifts
                }
            )
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        fac = Facility.objects.get(acronym__iexact=self.kwargs['fac'])
        cycle = ReviewCycle.objects.get(pk=self.kwargs['cycle'])
        res, created = models.Reservation.objects.get_or_create(
            beamline=fac, cycle=cycle, kind=self.kwargs.get('pool', None)
        )
        models.Reservation.objects.filter(pk=res.pk).update(**data)
        return JsonResponse(
            {
                "url": self.get_success_url()
            }
        )


class ScheduleBeamTime(EventEditor):
    selector_template = "projects/project-selector.html"
    allow_reservations = True
    allowed_roles = ['administrator:uso']

    def check_allowed(self):
        self.facility = Facility.objects.filter(acronym__iexact=self.kwargs['fac']).first()
        return super().check_allowed() or self.facility.is_admin(self.request.user)

    def get_shift_config(self):
        from scheduler.models import ShiftConfig
        return ShiftConfig.objects.filter(duration=self.facility.shift_size).order_by('modified').last()

    def get_tags(self):
        return self.facility.tags()

    def get_api_urls(self):
        url = reverse('schedule-beamtime-api', kwargs={'pk': self.schedule.pk, 'fac': self.facility.acronym})
        return {
            'api': url, 'events': [reverse('schedule-modes-api', kwargs={'pk': self.schedule.pk}), url],
            'stats': reverse(
                'schedule-beamtime-stats-api', kwargs={'pk': self.schedule.pk, 'fac': self.facility.acronym}
            )
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cycle'] = self.schedule.cycle
        if self.facility.kind == Facility.TYPES.equipment:
            facilities = self.facility.utrace(stop=Facility.TYPES.village)
            context['allocations'] = models.Allocation.objects.filter(
                cycle=context['cycle'], beamline__in=facilities
            ).order_by('-shifts')
        else:
            context['allocations'] = models.Allocation.objects.filter(
                cycle=context['cycle'], beamline=self.facility
            ).order_by('-shifts')
        context['subtitle'] = self.facility.acronym
        return context


class BeamlineSchedule(RolePermsViewMixin, TemplateView):
    template_name = "scheduler/calendar.html"

    def get_context_data(self, **kwargs):
        from scheduler.models import ShiftConfig, Mode
        context = super().get_context_data(**kwargs)

        cur_date = self.request.GET.get('date', '')
        if not cur_date:
            cur_date = self.kwargs.get('date', timezone.now().date().isoformat())

        facility = Facility.objects.filter(acronym__iexact=self.kwargs['fac']).first()
        fac_children = [f.acronym for f in facility.dtrace() if
                        f.kind not in [facility.TYPES.village, facility.TYPES.sector]]

        config = ShiftConfig.objects.filter(duration=facility.shift_size).order_by('modified').last()
        shifts = config.shifts()

        context['default_date'] = cur_date
        context['timezone'] = settings.TIME_ZONE

        context['default_view'] = 'weekshift'
        context['sections'] = ','.join(fac_children + ['STAFF'])
        context['view_choices'] = 'weekshift,monthshift'
        context['shift_duration'] = config.duration
        context['shift_minutes'] = config.duration * 60
        context['shift_starts'] = [shift['time'] for shift in shifts]
        context['shifts'] = shifts
        context['shift_count'] = len(context['shift_starts'])
        context['mode_types'] = [{'code': k, 'name': v} for k, v in Mode.TYPES]
        context['subtitle'] = '{}'.format(facility.acronym)
        context['show_year'] = False
        context['tag_types'] = facility.tags()
        context['event_sources'] = [
            reverse('facility-modes-api'),
            reverse('support-schedule-api', kwargs={'fac': facility.acronym})] + [
            reverse('beamtime-schedule-api', kwargs={'fac': fac}) for fac in fac_children
        ]
        return context


class BeamTimeAPI(EventUpdateAPI):
    model = models.BeamTime
    serializer_class = serializers.BeamTimeSerializer
    creation_key = 'project'

    def get_queryset(self):
        self.queryset = super().get_queryset()
        self.facility = Facility.objects.filter(acronym=self.kwargs['fac']).first()
        self.queryset = self.queryset.filter(beamline=self.facility)
        return self.queryset

    def post_process(self, schedule, queryset, data):
        for m in data['project'].materials.filter(state=models.Material.STATES.pending):
            m.update_due_dates()

    def get_data(self, info):
        data = super().get_data(info)
        data.update(
            {
                'project': models.Project.objects.filter(pk=info.get('project')).first(), 'beamline': self.facility,
            }
        )
        return data


class BeamTimeListAPI(generics.ListAPIView):
    serializer_class = serializers.BeamTimeSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    parser_classes = (JSONParser,)

    def get_queryset(self):
        self.facility = Facility.objects.filter(acronym__iexact=self.kwargs['fac']).first()
        if self.request.GET.get('start') and self.request.GET.get('end'):
            start = self.request.GET.get('start')
            end = self.request.GET.get('end')
        else:
            today = timezone.now().date()
            start = today.replace(day=1)
            end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        filters = Q(start__lte=end, end__gte=start) & (Q(beamline=self.facility) | Q(beamline__children=self.facility))
        return models.BeamTime.objects.filter(filters)


class AskClarification(RequestClarification):
    reference_model = models.Project

    def form_valid(self, form):
        response = super().form_valid(form)
        project = self.get_reference()
        success_url = reverse_lazy('project-detail', kwargs={'pk': project.pk})
        full_url = "{}{}".format(getattr(settings, 'SITE_URL', ""), success_url)

        sent = []
        for user in [project.spokesperson, project.get_delegate(), project.leader()]:
            if not user:
                continue
            if isinstance(user, dict):
                recipient = [user['email']]
                name = "{first_name} {last_name}".format(**user)
            else:
                recipient = [user]
                name = user.get_full_name()
            if recipient not in sent:
                data = {
                    'name': name, 'title': project.title, 'clarification': self.object.question,
                    'respond_url': full_url,
                    'due_date': timezone.now().date() + timedelta(days=3),
                }
                notify.send(recipient, 'clarification-requested', level=notify.LEVELS.important, context=data)
                sent.append(recipient)
        return response


class AnswerClarification(ClarificationResponse):
    reference_model = models.Project

    def check_allowed(self):
        project = self.get_reference()
        return super().check_allowed() or self.check_owner(project)

    def check_owner(self, obj):
        if obj:
            project = self.get_reference()
            return project.is_owned_by(self.request.user)
        else:
            return False

    def form_valid(self, form):
        super().form_valid(form)
        project = self.get_reference()

        review_ids = project.materials.filter(
            Q(state=models.Material.STATES.pending) & (
                Q(reviews__reviewer=self.object.requester) | (
                    Q(reviews__reviewer__isnull=True) & Q(reviews__role__in=self.object.requester.roles)))

        ).values_list('reviews', flat=True)
        reviews = models.Review.objects.filter(pk__in=review_ids)

        recipients = [self.object.requester]
        data = {
            'title': project.title, 'clarification': self.object.question, 'response': self.object.response,
            'reviews': reviews,
        }
        notify.send(recipients, 'clarification-received', level=notify.LEVELS.important, context=data)
        return JsonResponse({'url': ''})


class BeamtimeStatsAPI(EventStatsAPI):
    model = models.BeamTime
    group_by = 'project_id'

    def get_queryset(self):
        facility = Facility.objects.filter(acronym__iexact=self.kwargs['fac']).first()
        self.queryset = models.BeamTime.objects.filter(beamline=facility)
        return super().get_queryset()


class ShowClarifications(RolePermsViewMixin, detail.DetailView):
    model = models.Project
    template_name = 'proposals/clarifications.html'


class ShowAttachments(RolePermsViewMixin, detail.DetailView):
    model = models.Project
    template_name = 'proposals/attachments.html'


class DeleteSession(RolePermsViewMixin, ConfirmDetailView):
    model = models.Session
    template_name = "forms/delete.html"
    allowed_roles = ['administrator:uso']
    admin_roles = ['administrator:uso']

    def get_queryset(self):
        return super().get_queryset().filter(state=models.Session.STATES.ready)

    def check_allowed(self):
        session = self.get_object()
        facility = session.beamline

        return super().check_allowed() or facility.is_staff(self.request.user)

    def confirmed(self, *args, **kwargs):
        obj = self.get_object()
        project = obj.project
        obj.delete()
        messages.info(self.request, "Draft permit deleted!")
        return JsonResponse(
            {
                "url": reverse('project-detail', kwargs={'pk': project.pk})
            }
        )


# FIXME Needs review
class TeamMemberDelete(RolePermsViewMixin, ConfirmDetailView):
    model = models.Project
    template_name = "projects/forms/remove_team.html"
    allowed_roles = ['administrator:uso']
    admin_roles = ['administrator:uso']

    def check_allowed(self):
        return super().check_allowed() or self.request.user.pk == self.kwargs['user_pk']

    def get_success_url(self):
        return reverse('project-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['team'] = self.kwargs.get('user_pk')
        return context

    def confirmed(self, *args, **kwargs):
        user = User.objects.get(pk=self.kwargs.get('user_pk'))
        project = self.get_object()
        user_emails = {e.lower() for e in [_f for _f in [user.email, user.alt_email] if _f]}
        team_details = [t for t in project.details.get('team_members', []) if
                        t.get('email', '').lower() not in user_emails]
        project.details['team_members'] = team_details
        project.save()
        project.team.remove(user)

        msg = '{0} removed from project "{1}"'.format(user.get_full_name(), project)
        messages.success(self.request, msg)
        return JsonResponse(
            {
                "url": self.get_success_url()
            }
        )


class CreateAllocRequest(RolePermsViewMixin, edit.CreateView):
    model = models.AllocationRequest
    form_class = forms.AllocRequestForm
    template_name = "projects/forms/request_form.html"
    allowed_roles = ['administrator:uso']

    def check_allowed(self):
        self.facility = Facility.objects.get(acronym=self.kwargs.get('fac'))
        self.project = models.Project.objects.get(pk=self.kwargs.get('pk'))
        return (super().check_allowed() or self.check_owner(self.project))

    def check_owner(self, obj):
        return obj.project.is_owned_by(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cycle'] = models.ReviewCycle.objects.get(pk=self.kwargs.get('cycle'))
        context['project'] = models.Project.objects.get(pk=self.kwargs.get('pk'))
        context['facility'] = self.facility
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['facility'] = Facility.objects.get(acronym=self.kwargs.get('fac'))
        kwargs['form_title'] = "Allocation Request"
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        project = models.Project.objects.get(pk=self.kwargs.get('pk'))
        initial['shift_request'] = 1
        material = project.current_material()
        if material and material.siblings().pending().count():
            material = material.siblings().pending().first()
        initial['procedure'] = material.procedure
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        tags = data.pop('tags', [])
        form_action = data.pop('form_action')

        data['project'] = models.Project.objects.get(pk=self.kwargs.get('pk'))
        data['cycle'] = models.ReviewCycle.objects.get(pk=self.kwargs.get('cycle'))
        data['beamline'] = Facility.objects.get(acronym=self.kwargs.get('fac'))

        if form_action == 'submit':
            data['state'] = self.model.STATES.submitted

        self.object = self.model.objects.create(**data)
        self.object.tags.add(*tags)

        if form_action == 'save':
            success_url = reverse("edit-alloc-request", kwargs={'pk': self.object.pk})
            msg = 'Allocation Request was saved successfully'
        else:
            success_url = reverse("project-detail", kwargs={'pk': self.object.project.pk})
            msg = 'Allocation Request submitted'
        messages.add_message(self.request, messages.SUCCESS, msg)
        return HttpResponseRedirect(success_url)


class CreateShiftRequest(RolePermsViewMixin, edit.CreateView):
    model = models.ShiftRequest
    form_class = forms.ShiftRequestForm
    template_name = "projects/forms/request_form.html"
    allowed_roles = ['administrator:uso']

    def check_allowed(self):
        self.allocation = models.Allocation.objects.get(pk=self.kwargs.get('pk'))
        return (super().check_allowed() or self.check_owner(self.allocation.project))

    def check_owner(self, obj):
        return obj.project.is_owned_by(self.request.user)

    def get_initial(self):
        initial = super().get_initial()
        initial['shift_request'] = 1
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['facility'] = self.allocation.beamline
        kwargs['form_title'] = "Shift Request"
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cycle'] = self.allocation.cycle
        context['project'] = self.allocation.project
        context['facility'] = self.allocation.beamline
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        tags = data.pop('tags', [])
        form_action = data.pop('form_action')
        data['allocation'] = self.allocation

        if form_action == 'submit':
            data['state'] = self.model.STATES.submitted

        self.object = self.model.objects.create(**data)
        self.object.tags.add(*tags)

        if form_action == 'save':
            success_url = reverse("edit-shift-request", kwargs={'pk': self.object.pk})
            msg = 'Shift Request was saved successfully'
        else:
            success_url = reverse("project-detail", kwargs={'pk': self.object.allocation.project.pk})
            msg = 'Shift Request submitted'
        messages.add_message(self.request, messages.SUCCESS, msg)
        return HttpResponseRedirect(success_url)


class EditShiftRequest(RolePermsViewMixin, edit.UpdateView):
    model = models.ShiftRequest
    form_class = forms.ShiftRequestForm
    template_name = "projects/forms/request_form.html"
    edit_url = "edit-shift-request"
    allowed_roles = ['administrator:uso']

    def check_allowed(self):
        object = self.get_object()
        self.allocation = object.allocation
        return (super().check_allowed() or self.check_owner(self))

    def check_owner(self, obj):
        return obj.allocation.project.is_owned_by(self.request.user)

    def get_project(self):
        return self.object.allocation.project

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['facility'] = self.object.allocation.beamline
        kwargs['form_title'] = "Edit Shift Request"
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cycle'] = self.object.allocation.cycle
        context['project'] = self.object.allocation.project
        context['facility'] = self.object.allocation.beamline
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        tags = data.pop('tags', [])
        form_action = data.pop('form_action', 'save')
        if form_action == 'save':
            success_url = reverse(self.edit_url, kwargs={'pk': self.object.pk})
            msg = 'Shift Request was saved successfully'
        else:
            data['state'] = self.model.STATES.submitted
            success_url = reverse("project-detail", kwargs={'pk': self.get_project().pk})
            msg = 'Shift Request submitted'

        self.model.objects.filter(pk=self.object.pk).update(**data)
        self.object.tags.clear()
        self.object.tags.add(*tags)
        messages.add_message(self.request, messages.SUCCESS, msg)
        return HttpResponseRedirect(success_url)


class RequestPreferencesAPI(RolePermsViewMixin, View):
    allowed_roles = ["employee"]

    def get(self, *args, **kwargs):
        facility = Facility.objects.get(acronym__iexact=self.kwargs['fac'])
        project = models.Project.objects.get(pk=self.kwargs['pk'])
        alloc = models.Allocation.objects.filter(beamline=facility, project=project).last()
        start = parser.parse(self.request.GET['start'])
        end = parser.parse(self.request.GET['end'])

        good_dates = []
        poor_dates = []

        for req in itertools.chain(
                project.allocation_requests.all(), models.ShiftRequest.objects.filter(allocation__project=project).all()
        ):
            good_dates.extend([parser.parse(v) for v in [_f for _f in req.good_dates.split(',') if _f]])
            poor_dates.extend([parser.parse(v) for v in [_f for _f in req.poor_dates.split(',') if _f]])

        good_dates = [x for x in good_dates if start <= x <= end]
        poor_dates = [x for x in poor_dates if start <= x <= end]

        events = [{
            'start': d.isoformat(), 'end': (d + timedelta(days=1)).isoformat(), 'name': 'Preferred Dates',
            'type': 'available',
            'rendering': 'preferences',
        } for d in good_dates] + [{
            'start': d.isoformat(), 'end': (d + timedelta(days=1)).isoformat(), 'type': 'unavailable',
            'rendering': 'preferences',
        } for d in poor_dates]
        return JsonResponse(events, safe=False)


class ProjectSchedule(RolePermsViewMixin, detail.DetailView):
    model = models.Project
    template_name = "scheduler/calendar.html"
    allowed_roles = ['employee:hse', 'administrator:uso']
    admin_roles = ['administrator:uso']

    def check_allowed(self):
        self.project = self.get_object()
        return (super().check_allowed() or self.project.team.filter(
            username=self.request.user.username
        ).exists() or self.check_admin() or self.check_owner(self.project))

    def check_admin(self):
        return (super().check_admin() or any(fac.is_staff(self.request.user) for fac in self.project.beamlines.all()))

    def check_owner(self, obj):
        return obj.is_owned_by(self.request.user)

    def get_context_data(self, **kwargs):
        from scheduler.models import ShiftConfig, Mode
        context = super().get_context_data(**kwargs)
        cur_date = self.kwargs.get('date', timezone.now().date().isoformat())

        slot = min(self.project.beamlines.values_list('shift_size', flat=True))
        config = ShiftConfig.objects.filter(duration=slot).order_by('modified').last()
        shifts = config.shifts()

        context['default_date'] = cur_date
        context['default_view'] = 'monthshift'
        context['timezone'] = settings.TIME_ZONE
        context['shift_duration'] = config.duration
        context['shift_minutes'] = config.duration * 60
        context['shift_starts'] = [shift['time'] for shift in shifts]
        context['shifts'] = shifts
        context['shift_count'] = len(context['shift_starts'])
        context['mode_types'] = [{'code': k, 'name': v} for k, v in Mode.TYPES]
        context['subtitle'] = '{} Schedule'.format(self.project)
        context['show_year'] = False
        context['event_sources'] = [reverse('facility-modes-api'),
                                    reverse('project-schedule-api', kwargs={'pk': self.project.pk}), ]
        return context


class ProjectScheduleAPI(generics.ListAPIView):
    serializer_class = serializers.ProjectBeamTimeSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    parser_classes = (JSONParser,)

    def get_queryset(self):
        self.project = models.Project.objects.filter(pk=self.kwargs['pk']).first()
        self.queryset = self.project.beamtimes
        if self.request.GET.get('start') and self.request.GET.get('end'):
            start = self.request.GET.get('start')
            end = self.request.GET.get('end')
            self.queryset = self.queryset.filter(start__lte=end, end__gte=start)
        return super().get_queryset()


class DeclineAllocation(RolePermsViewMixin, edit.UpdateView):
    model = models.Allocation
    template_name = "forms/modal.html"
    form_class = forms.DeclineForm
    allowed_roles = ['administrator:uso']

    def check_allowed(self):
        self.project = self.get_object().project
        return (super().check_allowed() or self.project.team.filter(
            username=self.request.user.username
        ).exists() or self.check_admin() or self.check_owner(self.project))

    def check_admin(self):
        return super().check_admin() or any(fac.is_staff(self.request.user) for fac in self.project.beamlines.all())

    def check_owner(self, obj):
        return obj.project.is_owned_by(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['allocation'] = self.object
        return context

    def form_valid(self, form):
        allocation = self.get_object()
        comments = "Allocation of {} shifts declined by {} on {}, reason: {}".format(
            allocation.shifts, self.request.user, timezone.localtime(timezone.now()), form.cleaned_data['comments']
        )

        data = {
            'allocation': allocation, 'shifts': allocation.shifts, 'comments': form.cleaned_data['comments'],
        }

        notify.send(
            ["beamline-admin:{}".format(allocation.beamline.acronym.lower())], 'allocation-declined',
            level=notify.LEVELS.important, context=data
        )
        models.Allocation.objects.filter(pk=allocation.pk).update(
            comments=comments, shifts=0, modified=timezone.localtime(timezone.now())
        )

        messages.warning(self.request, 'Your request to decline the allocation was processed')
        return JsonResponse(
            {
                "url": "",
            }
        )


class Statistics(RolePermsViewMixin, TemplateView):
    admin_roles = ['administrator:uso']
    allowed_roles = ['employee']
    template_name = "projects/statistics.html"


def _fmt_contact(user, obj=None):
    return '{} <br/><small>&lt;{}&gt;</small>'.format(user, user.email)


class InvoicingList(RolePermsViewMixin, ItemListView):
    model = models.Project
    paginate_by = 50
    template_name = "item-list.html"
    list_columns = ['code', 'kind', 'get_leader', 'invoice_email', 'pretty_invoice_address', 'shifts_allocated',
                    'shifts_used']
    csv_fields = ['code', 'kind', 'get_leader', 'invoice_email', 'invoice_place', 'invoice_street', 'invoice_city',
                  'invoice_region',
                  'invoice_country', 'invoice_code', 'shifts_allocated', 'shifts_used']
    list_filters = ['start_date', 'end_date', 'kind', BeamlineFilterFactory.new("beamlines")]
    list_search = ['proposal__title', 'proposal__team', 'id']
    list_styles = {'title': 'col-xs-3', 'state': 'text-center', 'beamlines': 'col-xs-2'}
    list_transforms = {
        'beamlines': _fmt_beamlines,
    }
    link_url = "project-detail"
    order_by = ['-cycle__start_date', '-created']
    list_title = 'Invoicing'
    admin_roles = ['administrator:uso']
    allowed_roles = ['administrator:uso']

    def get_list_title(self):
        cycle = ReviewCycle.objects.get(pk=self.kwargs['pk'])
        return '{} Invoicing'.format(cycle)

    def get_queryset(self, *args, **kwargs):
        cycle = ReviewCycle.objects.get(pk=self.kwargs['pk'])
        self.queryset = models.Project.objects.filter(allocations__cycle=cycle, allocations__declined=False).annotate(
            shifts_allocated=Sum('allocations__shifts'), shifts_used=Sum(
                Case(
                    When(
                        sessions__start__gte=cycle.start_date, sessions__end__lt=cycle.end_date,
                        sessions__state=models.Session.STATES.complete,
                        then=Shifts(F('sessions__end'), F('sessions__start'))
                    ), default=0, output_field=IntegerField()
                )
            )
        ).exclude(shifts_allocated=0)
        return super().get_queryset(*args, **kwargs)
