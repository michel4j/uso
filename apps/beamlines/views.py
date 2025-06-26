import calendar
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponseRedirect, Http404, HttpResponseNotFound
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.generic import TemplateView, detail
from django.views.generic import edit
from itemlist.views import ItemListView
from rest_framework import generics, permissions
from rest_framework.parsers import JSONParser

from projects.models import LabSession
from proposals.filters import TechniqueFilterFactory
from roleperms.views import RolePermsViewMixin
from scheduler.views import EventUpdateAPI, EventEditor, EventStatsAPI
from . import forms
from . import models
from . import serializers

USO_ADMIN_ROLES = getattr(settings, 'USO_ADMIN_ROLES', ["admin:uso"])
USO_STAFF_ROLES = getattr(settings, 'USO_STAFF_ROLES', ["staff"])


class BeamlineList(RolePermsViewMixin, ItemListView):
    model = models.Facility
    template_name = "tooled-item-list.html"
    tool_template = "beamlines/list-tools.html"
    admin_roles = USO_ADMIN_ROLES
    list_title = 'Facilities'
    list_columns = ['name', 'acronym', 'kind', 'state']
    link_url = 'facility-detail'
    paginate_by = 20
    list_filters = {'state', 'kind', TechniqueFilterFactory.new()}
    list_search = ['acronym', 'name', 'port']
    ordering = ['kind', '-state', 'name']


def _fmt_codes(bls, obj=None):
    return ', '.join([bl.code for bl in bls.distinct()])


class LaboratoryList(RolePermsViewMixin, ItemListView):
    model = models.Lab
    template_name = "item-list.html"
    admin_roles = USO_ADMIN_ROLES
    list_title = 'Laboratories'
    list_columns = ['name', 'acronym', 'permission_names', 'num_workspaces', 'available']
    link_url = 'lab-detail'
    paginate_by = 20
    list_filters = {'created', 'modified', 'available', }
    list_search = ['acronym', 'name', 'description', 'permissions__code']
    order_by = ['available', 'name']


class BeamlineDetail(RolePermsViewMixin, detail.DetailView):
    template_name = 'beamlines/detail.html'
    model = models.Facility
    admin_roles = USO_ADMIN_ROLES

    def get_object(self, *args, **kwargs):
        if self.kwargs.get('fac'):
            object = models.Facility.objects.filter(acronym__iexact=self.kwargs['fac']).first()
            if not object:
                raise Http404
            return object
        return super().get_object(*args, **kwargs)

    def check_admin(self):
        facility = self.get_object()
        return super().check_admin() or facility.is_admin(self.request.user)

    def check_owner(self, obj):
        return obj.is_admin(self.request.user)

    def get_context_data(self, **kwargs):
        from proposals.models import ReviewCycle, ConfigItem
        context = super().get_context_data(**kwargs)
        filters = Q(config__facility=self.object)
        parent = self.object.parent
        while parent:
            filters |= Q(config__facility=parent)
            parent = parent.parent
        config_items = ConfigItem.objects.filter(filters)
        if config_items.count():
            six_months_ago = (timezone.now() - timedelta(days=178)).date()
            context['cycles'] = ReviewCycle.objects.filter(end_date__gte=six_months_ago).order_by('start_date')[:4]
        return context


class LaboratoryDetail(RolePermsViewMixin, detail.DetailView):
    template_name = 'beamlines/lab.html'
    model = models.Lab
    admin_roles = USO_ADMIN_ROLES
    allowed_roles = USO_STAFF_ROLES


class FacilityDetails(RolePermsViewMixin, TemplateView):
    template_name = 'beamlines/proposal_specs.html'

    def get_context_data(self, **kwargs):
        from users.models import User
        context = super().get_context_data(**kwargs)
        if self.kwargs.get('pk'):
            self.object = models.Facility.objects.get(pk=self.kwargs['pk'])
            context['object'] = context['facility'] = self.object
            contact_role = "beamline-admin:{}".format(self.object.acronym.lower())
            config = self.object.configs.first()
            contacts = User.objects.all_with_roles(contact_role)
            context['contacts'] = contacts
            context['config'] = config
        return context


class FacilityTags(RolePermsViewMixin, detail.DetailView):
    template_name = 'beamlines/fields/facility_tags.html'
    model = models.Facility

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.GET.get('tags'):
            tag_pks = self.request.GET.get('tags').split(',')
            selected = self.object.tags().filter(pk__in=tag_pks)
        else:
            selected = []
        context['choices'] = [(tag, tag in selected) for tag in self.object.tags().all()]
        context['field_name'] = self.kwargs.get('field_name')
        return context


class CreateFacility(RolePermsViewMixin, edit.CreateView):
    form_class = forms.FacilityForm
    template_name = "form.html"
    model = models.Facility
    success_url = reverse_lazy('beamline-list')
    allowed_roles = USO_ADMIN_ROLES

    def get_initial(self):
        initial = super().get_initial()
        for f, v in [('staff', 10), ('maintenance', 10), ('purchased', 25), ('beamteam', 10), ('user', 45)]:
            initial['time_{}'.format(f)] = v
        return initial


class EditFacility(RolePermsViewMixin, edit.UpdateView):
    form_class = forms.FacilityForm
    template_name = "form.html"
    model = models.Facility
    success_url = reverse_lazy('beamline-list')
    allowed_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        self.facility = self.get_object()
        return (
            super().check_allowed() or
            self.facility.is_admin(self.request.user)
        )

    def check_owner(self, obj):
        return obj.is_admin(self.request.user)

    def get_success_url(self):
        success_url = reverse("facility-detail", kwargs={'pk': self.object.pk})
        return success_url

    def form_valid(self, form):
        data = form.cleaned_data
        data['modified'] = timezone.now()
        self.model.objects.filter(pk=self.object.pk).update(**data)
        return HttpResponseRedirect(self.get_success_url())

    def get_initial(self):
        initial = super().get_initial()
        facility = self.get_object()
        beamtime = facility.details.get('beamtime', {})
        for f in ['staff', 'maintenance', 'purchased', 'beamteam', 'user']:
            initial[f'time_{f}'] = beamtime.get(f, 0)
        initial['public_support'] = facility.details.get('public_support', False)
        return initial


class UserSupportAPI(EventUpdateAPI):
    model = models.UserSupport
    serializer_class = serializers.UserSupportSerializer
    creation_key = 'staff'

    def get_queryset(self):
        self.queryset = super().get_queryset()
        self.facility = models.Facility.objects.filter(acronym=self.kwargs['fac']).first()
        self.queryset = self.queryset.filter(facility=self.facility)
        return self.queryset

    def get_data(self, info):
        data = super().get_data(info)
        data.update(
            {
                'staff': get_user_model().objects.filter(username=info.get('staff')).first(),
                'facility': self.facility,
            }
        )
        return data


class UserSupportListAPI(generics.ListAPIView):
    serializer_class = serializers.UserSupportSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    parser_classes = (JSONParser,)

    def get_queryset(self):
        self.facility = models.Facility.objects.filter(acronym__iexact=self.kwargs['fac']).first()
        if self.request.GET.get('start') and self.request.GET.get('end'):
            start = self.request.GET.get('start')
            end = self.request.GET.get('end')
        else:
            today = timezone.now().date()
            start = today.replace(day=1)
            end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        filters = Q(start__lte=end, end__gte=start) & (Q(facility=self.facility) | Q(facility__children=self.facility))
        return models.UserSupport.objects.filter(filters)


class ScheduleSupport(EventEditor):
    selector_template = "beamlines/support-selector.html"

    def check_allowed(self):
        self.facility = models.Facility.objects.filter(pk=self.kwargs['fac']).first()
        return (
                super().check_allowed() or
                self.facility.is_admin(self.request.user)
        )

    def get_shift_config(self):
        from scheduler.models import ShiftConfig
        return ShiftConfig.objects.filter(duration=self.facility.shift_size).order_by('modified').last()

    def get_api_urls(self):
        url = reverse('schedule-support-api', kwargs={'pk': self.schedule.pk, 'fac': self.facility.acronym})
        return {
            'api': url,
            'events': [
                reverse('schedule-modes-api', kwargs={'pk': self.schedule.pk}),
                url
            ],
            'stats': reverse(
                'schedule-support-stats-api', kwargs={'pk': self.schedule.pk, 'fac': self.facility.acronym}
            )
        }

    def get_context_data(self, **kwargs):
        from users.models import User
        context = super().get_context_data(**kwargs)
        context['cycle'] = self.schedule.cycle
        if self.facility.kind == models.Facility.TYPES.equipment:
            fac = self.facility.parent
        else:
            fac = self.facility
        role = "beamline-staff:{}".format(self.facility.acronym.lower())
        context['staff'] = User.objects.all_with_roles(role)
        return context


class UserSupportStatsAPI(EventStatsAPI):
    model = models.UserSupport
    group_by = 'staff_id'

    def get_queryset(self):
        facility = models.Facility.objects.filter(acronym__iexact=self.kwargs['fac']).first()
        self.queryset = models.UserSupport.objects.filter(facility=facility)
        return super().get_queryset()


def _fmt_localtime(datetime, obj=None):
    return timezone.localtime(datetime).strftime('%Y-%m-%d %H:%M')


class LaboratoryHistory(RolePermsViewMixin, ItemListView):
    model = LabSession
    template_name = "item-list.html"
    paginate_by = 25
    list_columns = ['project', 'lab__acronym', 'workspaces__name', 'spokesperson', 'start', 'end']
    list_filters = ['created', 'modified', 'start', 'end']
    list_search = [
        'project__title', 'project__spokesperson__username', 'project__id', 'project__spokesperson__last_name',
        'project__spokesperson__first_name', 'id', 'workspaces__name'
    ]
    list_transforms = {'start': _fmt_localtime, 'end': _fmt_localtime}
    link_url = "lab-permit"
    order_by = ['-modified']
    admin_roles = USO_ADMIN_ROLES
    allowed_roles = USO_STAFF_ROLES

    def get_list_title(self):
        return "{} Session History".format(self.lab)

    def get_queryset(self):
        self.queryset = self.lab.lab_sessions.filter()
        return super().get_queryset()

    def check_allowed(self):
        from beamlines.models import Lab
        self.lab = Lab.objects.get(pk=self.kwargs['pk'])
        allowed = (
                super().check_allowed() or
                self.check_admin()
        )
        return allowed
