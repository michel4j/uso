import json

from crisp_modals.views import ModalUpdateView, ModalCreateView, ModalDeleteView
from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import When, Case, Value, BooleanField, Q
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, View, detail
from itemlist.views import ItemListView

from misc.models import ActivityLog
from misc.utils import is_ajax
from misc.views import JSONResponseMixin
from roleperms.views import RolePermsViewMixin
from . import forms
from . import models

MAX_RESULTS = 30

USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ['admin:uso'])
USO_STAFF_ROLES = getattr(settings, "USO_STAFF_ROLES", ['staff'])
USO_CURATOR_ROLES = getattr(settings, "USO_CURATOR_ROLES", ['curator:publications'])
USO_HSE_ROLES = getattr(settings, "USO_HSE_ROLES", ['staff:hse'])


class HSDBSearch(RolePermsViewMixin, TemplateView):
    template_name = 'samples/inline-search.html'

    def get_context_data(self, **kwargs):
        try:
            from fuzzywuzzy import process
        except ImportError:
            process = None

        context = super().get_context_data(**kwargs)
        search_string = self.request.GET.get('q')

        if search_string:
            if not process:
                substances = models.HazardousSubstance.objects.filter(Q(name__icontains=search_string))[:MAX_RESULTS]
            else:
                # Use fuzzywuzzy to find the best matches
                choices = dict(models.HazardousSubstance.objects.values_list('pk', 'name'))
                hits = process.extract(search_string, choices, limit=MAX_RESULTS)
                id_list = [v[-1] for v in hits]
                results = models.HazardousSubstance.objects.in_bulk(id_list)
                substances = filter(None, [results.get(pk) for pk in id_list])

            context['results'] = substances
            context['search_string'] = search_string
        return context


class HSDBRecord(JSONResponseMixin, View):
    def get(self, *args, **kwargs):
        substance = models.HazardousSubstance.objects.get(pk=kwargs.get('pk'))
        signals = substance.hazards.values_list('signal', flat=True).distinct()
        pictograms = models.Pictogram.objects.filter(
            code__in=substance.hazards.exclude(pictograms__isnull=True).values_list('pictograms__code', flat=True))
        if 'danger' in signals:
            signal = 'danger'
        elif 'warning' in signals:
            signal = 'warning'
        else:
            signal = ""

        remove_exclamation = pictograms.filter(code='GHS06').exists()
        remove_exclamation |= (
                substance.hazards.filter(hazard__code='H334').exists() and pictograms.filter(code='GHS08').exists())
        remove_exclamation |= (substance.hazards.filter(
            hazard__code__in=['H314', 'H315', 'H317', 'H318', 'H319']).exists() and pictograms.filter(
            code='GHS05').exists())
        if remove_exclamation:
            pictograms = pictograms.exclude(code='GHS07')

        result = {
            'name': substance.name,
            'description': substance.description,
            'kind': 'chemical',
            'hazard_types': [str(val) for val in pictograms.values_list('pk', flat=True)],
            'hazards': json.dumps(list(substance.hazards.values_list('pk', flat=True))),
            'signal': signal,
        }
        return self.render_to_response(result)


class SampleHelp(RolePermsViewMixin, TemplateView):
    template_name = "samples/fields/help.html"
    HELP = {
        "10": "What type of radioactive source (sample/sealed-source/device), radioisotope and specific activity",
        "5": "Describe cylinder volume, pressure and planned flow-rate",
        "gmo": "Describe the source organism, gene/function, vector and host recipient",
        "nano": "Is the nano-material fixed or free particulate",
    }
    for k in models.Sample.ETHICS_TYPES:
        HELP[k] = "Include ethics certificate number and expiry date"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['help'] = "Please provide more details."

        kind = self.request.GET.get('kind', '')
        state = self.request.GET.get('state', '')
        hazard_types = self.request.GET.get('pictograms', '').split(',')
        help_text = [x for x in [self.HELP.get(k) for k in [kind, state] + hazard_types] if x]
        if help_text:
            context['help'] = '; '.join(help_text)
        return context


class SampleField(RolePermsViewMixin, TemplateView):
    template_name = 'samples/fields/one_sample.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sample = models.Sample.objects.filter(pk=self.kwargs.get('pk')).first()
        if sample:
            context['sample'] = sample
            context['field_name'] = self.kwargs.get('field_name')
        return context


class SampleListView(RolePermsViewMixin, ItemListView):
    queryset = models.Sample.objects.all()
    template_name = "item-list.html"
    paginate_by = 15
    link_url = 'sample-edit-modal'
    link_attr = 'data-modal-url'
    list_filters = ['kind', 'state']
    list_columns = ['name', 'description', 'kind', 'state']
    list_search = ['name', 'description', 'state', 'kind']
    order_by = ['-created', ]
    owner_field = 'owner'
    allowed_roles = USO_ADMIN_ROLES + USO_HSE_ROLES


class UserSampleListView(SampleListView):
    template_name = "samples/list.html"
    allowed_roles = []
    list_title = 'My Samples'

    def get_queryset(self, *args, **kwargs):
        self.queryset = models.Sample.objects.filter(owner=self.request.user)
        return super().get_queryset()


class SampleCreate(SuccessMessageMixin, RolePermsViewMixin, ModalCreateView):
    form_class = forms.SampleForm
    template_name = "samples/sample-forml.html"
    model = models.Sample
    success_url = reverse_lazy('sample-list')
    success_message = "Sample '%(name)s' has been created."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(form_action=self.request.get_full_path())
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        initial['owner'] = self.request.user.pk
        return initial

    def form_valid(self, form):
        super().form_valid(form)
        return http.JsonResponse({
            'pk': self.object.pk,
            'name': str(self.object),
            'event': 'uso:sample-created'
        })


class EditSample(SuccessMessageMixin, RolePermsViewMixin, ModalUpdateView):
    form_class = forms.SampleForm
    template_name = "samples/sample-forml.html"
    model = models.Sample
    success_url = reverse_lazy('sample-list')
    success_message = "Sample '%(name)s' has been updated."

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.model.objects.filter(owner=self.request.user)
        return super().get_queryset()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            form_action=self.request.get_full_path(),
            delete_url=reverse('sample-delete', kwargs={'pk': self.object.pk})
        )
        return kwargs

    def form_valid(self, form):
        if self.object.is_editable:
            response = super().form_valid(form)
        else:
            messages.error(self.request, f"The sample '{self.object.name}' is no longer editable!")
            response = http.HttpResponseRedirect(self.request.get_full_path())

        if is_ajax(self.request):
            return http.JsonResponse({
                'pk': self.object.pk,
                'name': str(self.object),
                'event': 'uso:sample-updated',
            })
        else:
            return response


class SampleDelete(RolePermsViewMixin, ModalDeleteView):
    model = models.Sample

    def get_success_url(self):
        return reverse('user-sample-list')

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.model.objects.filter(owner=self.request.user, is_editable=True)
        return super().get_queryset()


def get_hazard_categories(active_type: str = None) -> list:
    """
    Returns a list of hazard categories with their associated hazards and pictograms.

    :param active_type: The code of the active hazard type to highlight in the list.
    :return:
    """

    groups = []
    for p in models.Pictogram.objects.exclude(code__in=['RG1', 'RG2', 'RG3', 'RG4', '000']):
        hazards = p.hazards

        groups.append({
            'name': p.name,
            'active': p.code == active_type,
            'description': p.description,
            'hazards': hazards.order_by('hazard__code'),
            'image': f"/static/samples/pictograms/{p.code}.svg",
        })
    groups.append({
        'name': "Biohazardous infectious materials",
        'active': active_type in ['RG1', 'RG2', 'RG3', 'RG4'],
        'description': (
            "Materials which are or may contain microorganisms, nucleic acids or proteins that "
            "cause or are a probable cause of infection, with or without toxicity, in humans or animals."
        ),
        'hazards': models.Hazard.objects.filter(hazard__code__startswith='RG').order_by('hazard__code'),
        'image': "/static/samples/pictograms/RG.svg",
    })

    return groups


class SampleHazards(RolePermsViewMixin, detail.DetailView):
    template_name = "samples/forms/hazards-review.html"
    model = models.Sample

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['field_name'] = self.kwargs['field_name']

        selected_types = (
            set(self.object.hazard_types.all().values_list('code', flat=True)) |
            set(self.object.hazards.values_list('pictograms__code', flat=True))
        )
        active_type = 'GHS03' if not selected_types else list(selected_types)[0]
        context['categories'] = get_hazard_categories(active_type)
        return context


class SamplePermissions(RolePermsViewMixin, detail.DetailView):
    template_name = "samples/forms/permissions.html"
    model = models.Sample

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['field_name'] = self.kwargs['field_name']
        context['field'] = {"name": 'sample_permission'}
        return context


class SafetyPermissionList(RolePermsViewMixin, ItemListView):
    model = models.SafetyPermission
    template_name = "item-list.html"
    paginate_by = 15
    link_url = 'edit-safety-permission'
    link_attr = 'data-modal-url'
    add_modal_url = 'add-safety-permission'
    list_filters = ['created', 'modified', 'review']
    list_columns = ['code', 'description', 'review']
    admin_roles = USO_ADMIN_ROLES + USO_HSE_ROLES
    allowed_roles = USO_ADMIN_ROLES + USO_HSE_ROLES


class EditSafetyPermission(RolePermsViewMixin, ModalUpdateView):
    form_class = forms.SafetyPermissionForm
    model = models.SafetyPermission
    success_url = reverse_lazy('safety-permission-list')
    admin_roles = USO_ADMIN_ROLES
    allowed_roles = USO_ADMIN_ROLES + USO_HSE_ROLES

    def get_delete_url(self):
        if self.check_admin():
            return reverse('delete-safety-permission', kwargs={'pk': self.object.pk})
        return None


class AddSafetyPermission(RolePermsViewMixin, ModalCreateView):
    form_class = forms.SafetyPermissionForm
    model = models.SafetyPermission
    success_url = reverse_lazy('safety-permission-list')
    admin_roles = USO_ADMIN_ROLES
    allowed_roles = USO_ADMIN_ROLES


class DeleteSafetyPermission(RolePermsViewMixin, ModalDeleteView):
    model = models.SafetyPermission
    admin_roles = USO_ADMIN_ROLES
    allowed_roles = USO_ADMIN_ROLES


class HazardousSubstanceList(RolePermsViewMixin, ItemListView):
    model = models.HazardousSubstance
    template_name = "item-list.html"
    paginate_by = 15
    link_url = 'edit-hazardous-substance'
    link_attr = 'data-modal-url'
    add_modal_url = 'add-hazardous-substance'
    list_filters = ['created', 'modified']
    list_columns = ['name', 'description']
    list_search = ['name', 'description']
    admin_roles = USO_ADMIN_ROLES + USO_HSE_ROLES
    allowed_roles = USO_ADMIN_ROLES + USO_HSE_ROLES


class EditHazardousSubstance(RolePermsViewMixin, ModalUpdateView):
    form_class = forms.HazardousSubstanceForm
    model = models.HazardousSubstance
    template_name = "samples/forms/hazards-form.html"
    success_url = reverse_lazy('hazardous-substance-list')
    admin_roles = USO_ADMIN_ROLES + USO_HSE_ROLES
    allowed_roles = USO_ADMIN_ROLES + USO_HSE_ROLES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['saved_hazards'] = list(self.object.hazards.values_list('pk', flat=True))
        selected_types = set(self.object.hazards.values_list('pictograms__code', flat=True))
        active_type = 'GHS03' if not selected_types else list(selected_types)[0]
        context['categories'] = get_hazard_categories(active_type)
        context['sample'] = self.object
        return context

    def get_initial(self):
        initial = super().get_initial()
        initial['saved_hazards'] = json.dumps(list(self.object.hazards.values_list('pk', flat=True)))
        return initial

    def get_delete_url(self):
        if self.check_admin():
            return reverse('delete-hazardous-substance', kwargs={'pk': self.object.pk})
        return None

    def form_valid(self, form):
        hazards = form.cleaned_data.pop('hazard_list', models.Hazard.objects.none())
        super().form_valid(form)
        self.object.hazards.set(hazards)
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.modify, description='Hazardous Substance Modified',
        )
        return http.JsonResponse({'message': "Hazardous substance has been updated."})


class AddHazardousSubstance(RolePermsViewMixin, ModalCreateView):
    form_class = forms.HazardousSubstanceForm
    model = models.HazardousSubstance
    template_name = "samples/forms/hazards-form.html"
    success_url = reverse_lazy('hazardous-substance-list')
    admin_roles = USO_ADMIN_ROLES + USO_HSE_ROLES
    allowed_roles = USO_ADMIN_ROLES + USO_HSE_ROLES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = get_hazard_categories()
        return context

    def form_valid(self, form):
        hazards = form.cleaned_data.pop('hazard_list', models.Hazard.objects.none())
        super().form_valid(form)
        self.object.hazards.set(hazards)
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.add, description='Hazardous Substance Added',
        )
        return http.JsonResponse({'message': "Hazardous substance has been added."})


class DeleteHazardousSubstance(RolePermsViewMixin, ModalDeleteView):
    model = models.HazardousSubstance
    admin_roles = USO_ADMIN_ROLES + USO_HSE_ROLES
    allowed_roles = USO_ADMIN_ROLES + USO_HSE_ROLES

    def get_success_url(self):
        return reverse('hazardous-substance-list')
