import json

from django import http
from django.contrib import messages
from django.contrib.admin.utils import NestedObjects
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse, reverse_lazy
from django.db import DEFAULT_DB_ALIAS
from django.db.models import When, Case, Value, BooleanField, Q
from django.utils.text import capfirst
from django.views.generic import TemplateView, View, detail
from django.views.generic.edit import CreateView, UpdateView

from . import forms
from . import models
from misc.utils import is_ajax
from misc.views import ConfirmDetailView
from misc.views import JSONResponseMixin
from itemlist.views import ItemListView
from roleperms.views import RolePermsViewMixin

MAX_RESULTS = 30


class HSDBSearch(RolePermsViewMixin, TemplateView):
    template_name = 'samples/inline-search.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_string = self.request.GET.get('q')
        choices = {h.pk: h.name for h in models.HazardousSubstance.objects.all()}
        if search_string:
            # results = models.HazardousSubstance.objects.filter(Q(name__icontains=search_string)|Q(description__icontains=search_string))[:15]
            results = models.HazardousSubstance.objects.filter(Q(name__icontains=search_string))[:MAX_RESULTS]
            """
            # fuzzy search
            hits = process.extract(search_string, choices, limit=MAX_RESULTS)
            hit_ids = [v[-1] for v in hits]
            samples = models.HazardousSubstance.objects.in_bulk(hit_ids)
            results = filter(None, [samples.get(pk) for pk in hit_ids])
            """
            context['results'] = results
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
    link_attr = 'data-url'
    list_filters = ['kind', 'state']
    list_columns = ['name', 'description', 'kind', 'state']
    list_styles = {'name': "col-xs-4", 'description': 'col-xs-4'}
    list_search = ['name', 'description', 'state', 'kind']
    order_by = ['-created', ]
    owner_field = 'owner'
    allowed_roles = ['administrator:uso']


class UserSampleListView(SampleListView):
    template_name = "samples/list.html"
    allowed_roles = []
    list_title = 'My Samples'

    def get_queryset(self, *args, **kwargs):
        self.queryset = models.Sample.objects.filter(owner=self.request.user)
        return super().get_queryset()


class SampleCreate(SuccessMessageMixin, RolePermsViewMixin, CreateView):
    form_class = forms.SampleForm
    template_name = "samples/forms/modal.html"
    model = models.Sample
    success_url = reverse_lazy('sample-list')
    success_message = "Sample '%(name)s' has been created."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['submit_url'] = reverse_lazy('add-sample-modal')
        return context

    def get_initial(self):
        initial = super().get_initial()
        initial['owner'] = self.request.user.pk
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(request=self.request)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        if is_ajax(self.request):
            return http.JsonResponse({
                'pk': self.object.pk,
                'name': str(self.object),
            })
        else:
            return response


class EditSample(SuccessMessageMixin, RolePermsViewMixin, UpdateView):
    form_class = forms.SampleForm
    template_name = "samples/forms/modal.html"
    model = models.Sample
    success_url = reverse_lazy('sample-list')
    success_message = "Sample '%(name)s' has been updated."

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.model.objects.filter(owner=self.request.user)
        return super().get_queryset()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(request=self.request)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['submit_url'] = reverse_lazy('sample-edit-modal', kwargs={'pk': self.object.pk})
        return context

    def form_valid(self, form):
        if self.object.is_editable:
            response = super().form_valid(form)
        else:
            messages.error(self.request, "The sample '{}' is no longer editable!".format(self.object.name))
            response = http.HttpResponseRedirect(self.request.get_full_path())

        if is_ajax(self.request):
            return http.JsonResponse({
                'pk': self.object.pk,
                'name': str(self.object),
            })
        else:
            return response


class SampleDelete(RolePermsViewMixin, ConfirmDetailView):
    model = models.Sample
    template_name = "samples/forms/delete.html"

    def get_success_url(self):
        return reverse('user-sample-list')

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.model.objects.filter(owner=self.request.user, is_editable=True)
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        collector = NestedObjects(using=DEFAULT_DB_ALIAS)  # database name
        collector.collect([context['object']])  # list of objects. single one won't do
        context['related'] = collector.nested(lambda x: '{}: {}'.format(capfirst(x._meta.verbose_name), x))
        return context

    def confirmed(self, *args, **kwargs):
        obj = self.get_object()
        msg = 'Sample "{}" deleted'.format(obj)
        obj.delete()
        messages.success(self.request, msg)
        return http.JsonResponse({"url": self.get_success_url()})


class SampleHazards(RolePermsViewMixin, detail.DetailView):
    template_name = "samples/forms/hazards.html"
    model = models.Sample

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hazard_pks = json.loads(self.request.GET.get('hazards', '[]')) or [0]
        context['field_name'] = self.kwargs['field_name']

        selected_types = (
                set(self.object.hazard_types.all().values_list('code', flat=True)) |
                set(self.object.hazards.values_list('pictograms__code', flat=True))
        )
        active_type = 'GHS03' if not selected_types else list(selected_types)[0]
        annotation = {
            'selected': Case(When(pk__in=hazard_pks, then=Value(True)), default=Value(False),
                             output_field=BooleanField())
        }

        groups = []
        for p in models.Pictogram.objects.exclude(code__in=['RG1', 'RG2', 'RG3', 'RG4', '000']):
            if p.code == 'GHS09':
                hazards = models.Hazard.objects.filter(hazard__code__startswith='H4')
            elif p.code == 'GHS08':
                hazards = p.hazards.filter() | models.Hazard.objects.filter(hazard__code__startswith='H36')
            elif p.code == 'GHS01':
                hazards = (p.hazards.filter() | models.Hazard.objects.filter(hazard__code__startswith='H20'))
            elif p.code == 'GHS02':
                hazards = (p.hazards.filter() | models.Hazard.objects.filter(hazard__code__startswith='H22'))
            elif p.code == 'GHS04':
                hazards = (p.hazards.filter() | models.Hazard.objects.filter(hazard__code__startswith='H28'))
            else:
                hazards = p.hazards

            groups.append({
                'name': p.name,
                'active': p.code == active_type,
                'description': p.description,
                'hazards': hazards.annotate(**annotation).order_by('hazard__code'),
                'image': "/static/samples/pictograms/{}.svg".format(p.code),
            })
        groups.append({
            'name': "Biohazardous infectious materials",
            'active': active_type in ['RG1', 'RG2', 'RG3', 'RG4'],
            'description': (
                "Materials which are or may contain microorganisms, nucleic acids or proteins that "
                "cause or are a probable cause of infection, with or without toxicity, in humans or animals."
            ),
            'hazards': models.Hazard.objects.filter(hazard__code__startswith='RG').annotate(**annotation).order_by(
                'hazard__code'),
            'image': "/static/samples/pictograms/RG.svg",
        })

        context['categories'] = groups
        return context


class SamplePermissions(RolePermsViewMixin, detail.DetailView):
    template_name = "samples/forms/permissions.html"
    model = models.Sample

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['field_name'] = self.kwargs['field_name']
        context['field'] = {"name": 'sample_permission'}
        return context
