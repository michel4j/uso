from crisp_modals.forms import ModalModelForm, ModalForm
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, HTML
from django import forms

from misc.forms import Fieldset, ModelPoolField
from . import models


class FacilityForm(forms.ModelForm):

    class Meta:
        model = models.Facility
        fields = ('name', 'kind', 'acronym', 'port', 'description', 'url', 'range', 'parent',
                  'state', 'spot_size', 'flux', 'resolution', 'source', 'flex_schedule',
                  'shift_size')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, }),
            'flex_schedule': forms.Select(choices=((True, "Yes"), (False, "No"))),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "facility-form"
        if self.instance.pk:
            self.helper.title = "Edit Facility"
        else:
            self.helper.title = "Create Facility"

        self.helper.layout = Layout(
            Div(
                Div('name', css_class="col-sm-8"),
                Div(Field('parent'), css_class="col-sm-4"),
                Div('acronym', css_class="col-sm-3"),
                Div(Field('kind'), css_class="col-sm-3"),
                Div(Field('url', placeholder="https:// ..."), css_class='col-sm-6'),
                Div('description', css_class='col-sm-12'),
                css_class="row"
            ),
            Fieldset(
                "Parameters",
                Div('source', required=True, css_class="col-sm-5"),
                Div('port', css_class="col-sm-2"),
                Div(Field('state'), css_class="col-sm-5"),
                Div('range', required=True, css_class="col-sm-6"),
                Div('flux', required=True, css_class="col-sm-6"),
                Div('resolution', required=True, css_class="col-sm-6"),
                Div('spot_size', required=True, css_class="col-sm-6")
            ),
            Div(
                Div(Field('flex_schedule'), css_class="col-sm-6"),
                Div(Field('shift_size'), css_class="col-sm-6"),
                css_class="row"
            ),
            HTML("<hr class='hr-xs'/>"),
            Div(
                Div(
                    StrictButton('Revert', type='reset', value='Reset', css_class="btn btn-secondary"),
                    StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary ms-auto'),
                    css_class="col-12 d-flex"
                ),
                css_class="row"
            )
        )

    def clean(self):
        data = super().clean()
        data['acronym'] = data.get('acronym', '').upper().replace('_', '-').replace(' ', '').strip()
        return data


class LabForm(ModalModelForm):
    class Meta:
        model = models.Lab
        fields = ('name', 'acronym', 'description', 'permissions', 'admin_roles', 'available')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.body.append(
            Div(
                Div('name', css_class="col-sm-8"),
                Div('acronym', css_class="col-sm-4"),
                Div('description', css_class="col-sm-12"),
                css_class="row"
            ),
            Div(
                Div(Field('permissions'), css_class="col-sm-12"),
                Div(Field('admin_roles'), css_class="col-sm-12"),
                Div(Field('available'), css_class="col-sm-12"),
                css_class="row"
            )
        )


class WorkspaceForm(ModalModelForm):
    class Meta:
        model = models.LabWorkSpace
        fields = ('lab', 'name', 'description', 'available')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, }),
            'lab': forms.HiddenInput
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.body.append(
            Div(
                Div('name', css_class="col-sm-12"),
                Div('description', css_class="col-sm-12"),
                Div(Field('available'), css_class="col-sm-12"),
                Field('lab'),
                css_class="row"
            )
        )