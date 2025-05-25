from datetime import datetime

import yaml
from crisp_modals.forms import ModalModelForm, Row, FullWidth
from crispy_forms.bootstrap import PrependedText, InlineCheckboxes
from crispy_forms.bootstrap import StrictButton, FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Div, Field, HTML
from django import forms
from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.urls import reverse_lazy
from django.utils.datastructures import MultiValueDict
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from model_utils import Choices

from proposals.templatetags.proposal_tags import humanize
from . import models
from .fields import FieldType
from .utils import Queryable, DotExpandedDict, build_Q, Crypt

SIZES = Choices(
    ('medium', _('Medium')),
    ('small', _('Small')),
    ('large', _('Large')),
)

LAYOUTS = Choices(
    ('full', _('Full')),
    ('half', _('Half')),
    ('third', _('Third')),
    ('quarter', _('Quarter')),
    ('two_thirds', _('Two Thirds')),
    ('three_quarters', _('Three Quarters')),
    ('auto', _('Auto')),
)
UNITS = Choices(
    ('chars', _('Characters')),
    ('words', _('Words')),
    ('value', _('Value')),
)

FIELD_OPTIONS = Choices(
    ('required', _('Required')),
    ('unique', _('Unique')),
    ('randomize', _('Randomize')),
    ('other', _('Add Other')),
)


class MultipleTextInput(forms.TextInput):
    def value_from_datadict(self, data, files, name):
        if isinstance(data, MultiValueDict):
            return data.getlist(name)
        return data.get(name, [])

    def compress(self, data_list):
        return data_list

    def decompress(self, value):
        return value


class RepeatableCharField(forms.MultipleChoiceField):
    widget = MultipleTextInput

    def validate(self, value):
        """
        Validates that the input is a list or tuple.
        """
        if self.required and not value:
            raise forms.ValidationError(self.error_messages['required'], code='required')


FIELD_SETTINGS = {
    'label': (forms.CharField, {'label': _("Label"), 'required': True}),
    'name': (forms.CharField, {'label': _("Field Name"), 'required': True}),
    'instructions': (forms.CharField, {'label': _("Instructions"), 'widget': forms.Textarea(attrs={'rows': 2})}),
    'tags': (forms.CharField, {'label': _("Style tags")}),
    'size': (forms.ChoiceField, {'label': _("Size")}),
    'width': (forms.ChoiceField, {'label': _("Width")}),
    'options': (forms.MultipleChoiceField, {'label': _("Options"), 'widget': forms.CheckboxSelectMultiple}),
    'minimum': (forms.FloatField, {'label': _("Min"), }),
    'maximum': (forms.FloatField, {'label': _("Max"), }),
    'units': (forms.ChoiceField, {'label': _("Units"), }),
    'default': (forms.CharField, {'label': _("Default value"), }),
    'choices': (RepeatableCharField, {'label': _("Choices"), 'required': True}),
    'values': (RepeatableCharField, {'label': _("Values"), 'required': False}),
    'default_choices': (RepeatableCharField, {'label': _("Default")}),
}

CHOICES_TEMPLATE = "{% include 'dynforms/field-choices.html' %}"


class FieldSettingsForm(forms.Form):
    def __init__(self, *args, **kwargs):
        field_type = kwargs.pop('field_type')
        action_url = kwargs.pop('action_url')
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_class = 'df-menu-form'
        self.helper.form_action = action_url
        if field_type is not None:
            self.helper.layout = Layout(
                self.create_layout(field_type)
            )
        else:
            self.helper.layout = Layout(
                HTML("""<div class="no-field panel panel-warning">
                <div class="panel-heading"><strong>No Field Selected</strong></div>
                <div class="panel-body">Please select a field on the form 
                preview to edit its settings.</div>
                </div>""")
            )

    def clean(self):
        cleaned_data = super().clean()
        if 'default_choices' in cleaned_data:
            cleaned_data['default_choices'] = list(map(int, cleaned_data['default_choices']))
            cleaned_data['default'] = [cleaned_data['choices'][i - 1] for i in cleaned_data['default_choices']]
        return cleaned_data

    def add_custom_field(self, name, **kwargs):
        ft, kw = FIELD_SETTINGS[name]
        kwargs.update(kw)
        kwargs['required'] = kwargs.get('required', False)
        self.fields[name] = ft(**kwargs)

    def create_layout(self, field_type):
        for nm in ['name', 'tags', 'label', 'instructions']:
            self.add_custom_field(nm)

        _fieldset = Fieldset(
            f"{field_type.name} - {_('Settings')}",
            'label',
            Field('instructions', rows=2)
        )

        for field_name in ['size', 'width', 'options']:
            if field_name in field_type.settings:
                self.add_custom_field(field_name, choices=field_type.get_choices(field_name))

        row = Div(css_class="row")
        for field_name in ['size', 'width']:
            if field_name in field_type.settings:
                row.append(Field(field_name, css_class='select col'))
        _fieldset.append(row)

        if 'options' in field_type.settings:
            _fieldset.append(Div(Div(InlineCheckboxes('options'), css_class='col-xs-12'), css_class="row"))

        if 'minimum' in field_type.settings or 'maximum' in field_type.settings or 'units' in field_type.settings:
            self.add_custom_field('minimum')
            self.add_custom_field('maximum')
            self.add_custom_field('units', choices=field_type.get_choices('units'))
            _fieldset.append(
                Div(
                    Div('minimum', css_class='col-xs-3'),
                    Div('maximum', css_class='col-xs-3'),
                    Div('units', css_class='col-xs-6'),
                    css_class="row"
                )
            )

        if 'choices' in field_type.settings:
            self.add_custom_field('default_choices')
            self.add_custom_field('choices')
            self.add_custom_field('values')

            choices = list(
                zip(self.initial.get('choices', []), self.initial.get('values', self.initial.get('choices', [])))
            )
            self.initial['choices_info'] = [{
                'label': i,
                'value': '' if v is None else v
            } for i, v in choices]

            self.initial['choices_type'] = field_type.choices_type
            _fieldset.append(HTML(CHOICES_TEMPLATE))

        elif 'default' in field_type.settings:
            self.add_custom_field('default')
            _fieldset.append('default'),

        _fieldset.append('tags')
        _fieldset.append(PrependedText(
            'name',
            mark_safe('<i class="bi-lightning text-danger"></i>'),
            title="This is the internal reference name for the field. Change with caution!"
        ))

        if self.initial.get('rules', []):
            RULE_HTML = "Rules <span class='badge'>%d</span>" % (len(self.initial['rules']))
        else:
            RULE_HTML = "Rules"

        _fieldset.append(
            FormActions(
                Div(
                    HTML('<hr class="hr-xs"/>'),
                    StrictButton('<i class="bi-box-arrow-in-left icon-fw"></i> Move to Prev Page', name='move-prev',
                                 value="move-prev",
                                 title="Move to Prev Page", css_class="btn btn-sm btn-light border pull-left"),
                    StrictButton('Move to Next Page <i class="bi-box-arrow-in-right icon-fw"></i>', name='move-next',
                                 value="move-next",
                                 title="Move to Next Page", css_class="btn btn-sm btn-light border pull-right"),
                    css_class="col-xs-12 text-condensed"),
                css_class="row")
        )
        _fieldset.append(FormActions(
            HTML('<hr class="hr-xs"/>'),
            StrictButton('Apply', name='apply-field', value="apply-field", css_class="btn btn-sm btn-primary"),
            StrictButton(RULE_HTML, name="edit-rules", value="edit-rules", css_class="btn btn-sm btn-secondary"),
            StrictButton('Delete', name='delete-field', value="delete-field",
                         css_class="btn btn-sm btn-danger pull-right"),
        ))
        return _fieldset


PAGES_TEMPLATE = "{% include 'dynforms/form-pages.html' %}"
ACTIONS_TEMPLATE = "{% include 'dynforms/form-actions.html' %}"


class FormSettingsForm(forms.ModelForm):
    page_names = RepeatableCharField(label=_("Pages"), required=True)
    action_names = RepeatableCharField(label=_("Action Buttons"), required=False)
    action_labels = RepeatableCharField(label=_("Action Buttons"), required=False)

    class Meta:
        model = models.FormType
        fields = ('code', 'name', 'description', 'page_names', 'actions', 'pages', 'action_names', 'action_labels')
        widgets = {
            'code': forms.TextInput(attrs={'placeholder': 'Unique slug, e.g. "feedback-form"'}),
            'name': forms.TextInput(attrs={'placeholder': 'Human friendly name'}),
            'description': forms.Textarea(
                attrs={'rows': 4, 'placeholder': 'Please provide a description content.'}
            ),
            'pages': forms.HiddenInput(),
            'actions': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_class = 'df-menu-form'
        delete_url = reverse_lazy('dynforms-delete-type', kwargs={'pk': self.instance.pk})
        self.helper.layout = Layout(
            Fieldset(
                _("Form Settings"),
                Div(
                    Div('code', css_class='col-xs-12'),
                    css_class="row"
                ),
                Div(
                    Div("name", css_class='col-xs-12'),
                    Div("description", css_class='col-xs-12'),
                    css_class="row"
                ),
                HTML(PAGES_TEMPLATE),
                HTML(ACTIONS_TEMPLATE),
                FormActions(
                    HTML('<hr class="hr-xs mt-5"/>'),
                    Div(
                        Submit('apply-form', 'Apply', css_class="btn-sm"),
                        HTML(
                            f'<a class="btn btn-sm btn-danger ms-auto" title="Delete Form" '
                            f'data-modal-url="{delete_url}"><i class="bi-trash"></i> Delete</a>'
                        ),
                        css_class="d-flex flex-row"
                    )
                ),
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['actions'] = list(zip(cleaned_data['action_names'], cleaned_data['action_labels']))

        if self.instance:
            pages = self.instance.pages
        else:
            pages = []

        titles = cleaned_data['page_names']
        for page, title in enumerate(titles):
            if page < len(pages):
                pages[page]['name'] = title
            else:
                pages.append({'name': title, 'fields': []})
        if len(pages) > len(titles) and len(pages[-1]['fields']) == 0:
            pages.pop()
        cleaned_data['pages'] = pages

        return cleaned_data


class RulesForm(forms.Form):
    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['rules'] = []
        data = DotExpandedDict(dict(self.data.lists()))
        if 'rule' in data:
            raw_rules = list(
                map(dict, list(zip(*[[(k, v) for v in value] for k, value in list(data['rule'].items())]))))
            cleaned_data['rules'] = [r for r in raw_rules if any(r.values())]
        return cleaned_data


class DynFormMixin:
    type_code = None
    field_specs: dict
    instance: models.DynEntry
    form_type: models.FormType
    initial: dict
    cleaned_data: dict

    def init_fields(self):

        self.initial['throttle'] = Crypt.encrypt(datetime.now().isoformat())
        if self.instance and hasattr(self.instance, 'form_type') and self.instance.form_type:
            self.form_type = self.instance.form_type
        else:
            self.form_type = models.FormType.objects.get(code=self.type_code)
            self.type_code = self.form_type.code

        self.field_specs = self.form_type.field_specs()

    def clean(self):
        super().clean()

        # convert dotted notation to nested dict
        if isinstance(self.data, QueryDict):
            data = DotExpandedDict(dict(self.data.lists()))
        else:
            data = DotExpandedDict(self.data)

        # convert lists (same as dotted notation but with an integer key)
        data = data.with_lists()
        self.cleaned_data['form_type'] = self.form_type
        cleaned_data, errors = self.custom_clean(data)
        self.cleaned_data['details'] = cleaned_data
        if errors:
            for field, error in errors.items():
                self.add_error(None, f'{humanize(field)}: {error}')
        return self.cleaned_data

    def custom_clean(self, data):
        cleaned_data = {}
        failures = {}
        submitting = False
        for name, label in self.form_type.actions:
            if label in data.get(name, []):
                cleaned_data["form_action"] = name
                submitting = (name == "submit")
                break

        # active page is a special numeric field, increment if save_continue
        field_type = FieldType.get_type('number')
        active_page = field_type.clean(data.get('active_page', 1), multi=False, validate=True)
        if cleaned_data['form_action'] == 'save_continue':
            cleaned_data['active_page'] = min(active_page + 1, len(self.form_type.pages) - 1)
        else:
            cleaned_data['active_page'] = active_page

        # extract field data
        for field_name, field_spec in self.field_specs.items():
            field_type = FieldType.get_type(field_spec['field_type'])
            multiple = "repeat" in field_spec.get('options', []) or field_type.multi_valued
            required = "required" in field_spec.get('options', [])

            if field_name in data:
                field_data = data.get(field_name)
                try:
                    cleaned_value = field_type.clean(field_data, multi=multiple, validate=submitting)
                except ValidationError as err:
                    failures[field_name] = err.message
                    cleaned_value = field_type.clean(field_data, multi=multiple, validate=False)
                if cleaned_value:
                    cleaned_data[field_name] = cleaned_value
            if submitting and required and not cleaned_data.get(field_name):
                failures[field_name] = "required"

        # second loop to check other validation
        q_data = Queryable(cleaned_data)
        for field_name, field_spec in list(self.field_specs.items()):
            req_rules = [r for r in field_spec.get('rules', []) if r['action'] == 'require']
            if req_rules:
                req_Q = build_Q(req_rules)
                if submitting and q_data.matches(req_Q) and not cleaned_data.get(field_name):
                    failures[field_name] = "required together with another field you have filled."

        return cleaned_data, failures


class DynForm(DynFormMixin, forms.ModelForm):
    class Meta:
        model = models.DynEntry
        fields = []

    def __init__(self, *args, **kwargs):
        self.form_type = kwargs.pop('form_type')
        super().__init__(*args, **kwargs)
        self.field_specs = self.form_type.field_specs()


class FormTypeForm(ModalModelForm):
    class Meta:
        model = models.FormType
        fields = ('code', 'name', 'description')
        widgets = {
            'code': forms.TextInput(attrs={'placeholder': 'Unique slug, e.g. "feedback-form"'}),
            'name': forms.TextInput(attrs={'placeholder': 'Human friendly name'}),
            'description': forms.Textarea(
                attrs={'rows': 4, 'placeholder': 'Please provide a description content.'}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)

        self.body.form_action = self.request.get_full_path()
        self.body.append(
            Row(
                FullWidth('code'),
                FullWidth("name"),
                FullWidth("description"),
            ),
        )
