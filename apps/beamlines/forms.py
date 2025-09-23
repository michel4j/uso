from crisp_modals.forms import ModalModelForm, ModalForm
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, HTML
from django import forms

from misc.fields import DelimitedTextFormField
from misc.forms import Fieldset, ModelPoolField
from . import models


class FacilityForm(forms.ModelForm):
    allocation = forms.ChoiceField(
        choices=((True, "Yes"), (False, "No")),
        required=False, label="Allocation Required",
        widget=forms.Select(choices=((True, "Yes"), (False, "No"))),
    )

    class Meta:
        model = models.Facility
        fields = ('name', 'kind', 'acronym', 'description', 'url', 'range', 'parent',
                  'state', 'spot_size', 'flux', 'resolution', 'source', 'flex_schedule',
                  'shift_size')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "facility-form"
        if self.instance.pk:
            self.helper.title = "Edit Facility"
            self.fields['allocation'].initial = not self.instance.flex_schedule
        else:
            self.helper.title = "Create Facility"

        self.helper.layout = Layout(
            Div(
                Div('name', css_class="col-sm-9"),
                Div('acronym', css_class="col-sm-3"),
                Div('kind', css_class="col-sm-3"),
                Div('parent', css_class="col-sm-3"),
                Div(Field('url', placeholder="https:// ..."), css_class='col-sm-6'),
                Div('description', css_class='col-sm-12'),
                css_class="row"
            ),
            Fieldset(
                "Parameters",
                Div('source', required=True, css_class="col-sm-6"),
                Div('state', css_class="col-sm-6"),
                Div('range', required=True, css_class="col-sm-6"),
                Div('flux', required=True, css_class="col-sm-6"),
                Div('resolution', required=True, css_class="col-sm-6"),
                Div('spot_size', required=True, css_class="col-sm-6")
            ),
            Div(
                Div(Field('allocation'), css_class="col-sm-6"),
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
        data['flex_schedule'] = not data.pop('allocation', True)
        return data


class LabForm(ModalModelForm):
    admin_roles = DelimitedTextFormField(required=False)

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
