from django.conf import settings
from django.urls import reverse_lazy
from django.forms.models import model_to_dict
from django.views.generic import TemplateView
from django.views.generic import edit
from django.views.generic.edit import FormView

from . import utils
from dynforms.fields import FieldType
from dynforms.models import FormType, FormSpec
from .forms import FieldSettingsForm, FormSettingsForm, RulesForm, DynForm
from misc.utils import load
from .models import DynEntry
from itemlist.views import ItemListView
from roleperms.views import RolePermsViewMixin

load('dynfields')

ADMIN_ROLES = ['developer-admin']


class DynFormViewMixin(object):
    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        if 'object' in context:
            context['active_page'] = context['object'].details.get('active_page', 0)
        else:
            context['active_page'] = 0
        return context


class DynUpdateView(DynFormViewMixin, edit.UpdateView):
    pass


class DynCreateView(DynFormViewMixin, edit.CreateView):
    pass


class DynFormView(RolePermsViewMixin, DynCreateView):
    allowed_roles = ADMIN_ROLES
    template_name = 'dynforms/test-form.html'
    form_class = DynForm
    model = DynEntry

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        form_spec = FormType.objects.get(pk=self.kwargs.get('pk')).spec
        kwargs['form_spec'] = form_spec
        return kwargs

    def form_valid(self, form):
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.get_full_path()


class AddFieldView(RolePermsViewMixin, TemplateView):
    allowed_roles = ADMIN_ROLES
    template_name = "dynforms/field.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = FormType.objects.get(pk=self.kwargs.get('pk')).spec
        field_type = FieldType.get_type(self.kwargs.get('type'))
        page = int(self.kwargs.get('page'))
        pos = int(self.kwargs.get('pos'))
        num = len(form.get_page(page)['fields'])
        field = field_type.get_default(page, num)
        form.add_field(page, pos, field)
        context['field'] = field
        print(context)
        return context


class GetFieldView(RolePermsViewMixin, TemplateView):
    allowed_roles = ADMIN_ROLES
    template_name = "dynforms/field.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = int(self.kwargs.get('page'))
        pos = int(self.kwargs.get('pos'))
        form = FormType.objects.get(pk=self.kwargs.get('pk')).spec
        field = form.get_field(page, pos)
        context['field'] = field
        return context


class MoveFieldView(RolePermsViewMixin, TemplateView):
    allowed_roles = ADMIN_ROLES
    template_name = 'dynforms/blank.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = int(self.kwargs.get('page'))
        pos = int(self.kwargs.get('pos'))
        src = int(self.kwargs.get('from'))
        form = FormType.objects.get(pk=self.kwargs.get('pk')).spec
        form.move_field(page, src, pos)
        return context


class PageFieldView(RolePermsViewMixin, TemplateView):
    allowed_roles = ADMIN_ROLES
    template_name = 'dynforms/blank.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = int(self.kwargs.get('page'))
        next_page = int(self.kwargs.get('to'))
        src = int(self.kwargs.get('pos'))
        form = FormType.objects.get(pk=self.kwargs.get('pk')).spec
        form.move_field(page, src, src, next_page)
        return context


RULE_ACTIONS = [
    ("", ""),
    ("show", "Show if"),
    ("hide", "Hide if"),
    ("require", "Require if"),
]


class FieldRulesView(RolePermsViewMixin, FormView):
    allowed_roles = ADMIN_ROLES
    template_name = 'dynforms/rule-editor.html'
    form_class = RulesForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = int(self.kwargs.get('page'))
        pos = int(self.kwargs.get('pos'))
        form = FormType.objects.get(pk=self.kwargs.get('pk')).spec
        field = form.get_field(page, pos)
        field['rules'] = field.get('rules', [])
        context['field'] = field
        context['page'] = form.get_page(page)
        context['field_choices'] = [(f['name'], f['label']) for p in form.pages
                                    for f in p['fields'] if
                                    ((f['field_type'] != 'new-section') and (f['label'] != field['label']))]
        context['action_url'] = reverse_lazy("dynforms-field-rules", kwargs={"pk": form.pk, "page": page, "pos": pos})
        context['field_operators'] = utils.FIELD_OPERATOR_CHOICES
        context['rule_actions'] = RULE_ACTIONS
        return context

    def form_valid(self, form):
        form_obj = FormSpec.objects.get(pk=self.kwargs.get('pk'))
        page = int(self.kwargs.get('page'))
        pos = int(self.kwargs.get('pos'))
        field = form_obj.get_field(page, pos)
        rules = form.cleaned_data['rules']
        field['rules'] = rules
        form_obj.update_field(page, pos, field)
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.get_full_path()


class DeleteFieldView(RolePermsViewMixin, TemplateView):
    allowed_roles = ADMIN_ROLES
    template_name = "dynforms/edit-settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = int(self.kwargs.get('page'))
        pos = int(self.kwargs.get('pos'))
        form = FormType.objects.get(pk=self.kwargs.get('pk')).spec
        form.remove_field(page, pos)
        return context


class EditFieldView(RolePermsViewMixin, FormView):
    allowed_roles = ADMIN_ROLES
    template_name = "dynforms/edit-settings.html"
    form_class = FieldSettingsForm

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        page = int(self.kwargs.get('page'))
        pos = int(self.kwargs.get('pos'))
        form = FormType.objects.get(pk=self.kwargs.get('pk')).spec
        field = form.get_field(page, pos)
        kw['field_type'] = FieldType.get_type(field['field_type'])
        kw['action_url'] = reverse_lazy("dynforms-put-field", kwargs={"pk": form.pk, "page": page, "pos": pos})
        kw['initial'] = field
        return kw

    def form_valid(self, form):
        page = int(self.kwargs.get('page'))
        pos = int(self.kwargs.get('pos'))
        form_obj = FormType.objects.get(pk=self.kwargs.get('pk')).spec
        field = form_obj.get_field(page, pos)
        field.update(form.cleaned_data)
        form_obj.update_field(page, pos, field)
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.get_full_path()


class EditFormView(RolePermsViewMixin, FormView):
    allowed_roles = ADMIN_ROLES
    template_name = 'dynforms/builder.html'
    form_class = FormSettingsForm

    def check_allowed(self):
        return super().check_allowed() and settings.DEBUG

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form_type = FormType.objects.get(pk=self.kwargs.get('pk'))
        form = form_type.spec
        initial = model_to_dict(form)
        initial.pop('pages')
        initial.pop('actions')
        initial['page_names'] = form.page_names()
        context['form_settings_form'] = FormSettingsForm(initial=initial)
        context['fieldtypes'] = FieldType.get_all()
        context['form_spec'] = form
        context['active_page'] = self.request.GET.get('page', 1)
        context['active_form'] = self.request.GET.get('form', 1)
        return context

    def form_valid(self, form):
        form_obj = FormType.objects.get(pk=self.kwargs.get('pk')).spec
        form_obj.actions = form.cleaned_data['actions']
        form_obj.update_pages(form.cleaned_data['page_names'])
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.get_full_path()


class DeletePageView(RolePermsViewMixin, TemplateView):
    allowed_roles = ADMIN_ROLES
    template_name = "dynforms/edit-settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = int(self.kwargs.get('page'))
        form = FormType.objects.get(pk=self.kwargs.get('pk')).spec
        form.remove_page(page)
        return context


class FormTypeList(RolePermsViewMixin, ItemListView):
    allowed_roles = ADMIN_ROLES
    queryset = FormType.objects.all()
    template_name = "item-list.html"
    paginate_by = 10
    link_url = 'dynforms-builder'
    list_columns = ['name', 'code', 'description', 'spec']
    list_filters = ['created', 'modified']
    list_styles = {'description': 'col-xs-6'}
    list_search = ['name', 'url_slug', 'description']
    order_by = ['-created']
