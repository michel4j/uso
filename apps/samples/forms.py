import json
import re

from crisp_modals.forms import ModalModelForm
from crispy_forms.bootstrap import FieldWithButtons, StrictButton, InlineCheckboxes
from crispy_forms.layout import Div, Field
from django import forms
from django.forms.widgets import HiddenInput

from . import models
from .widgets import HazardSelectMultiple, HiddenListInput


class SampleForm(ModalModelForm):
    class Meta:
        model = models.Sample
        fields = ('owner', 'name', 'source', 'kind', 'description', 'state', 'hazard_types', 'hazards')
        widgets = {
            'owner': HiddenInput(),
            'hazard_types': HazardSelectMultiple(),
            'hazards': HiddenListInput(),
            'description': forms.Textarea(
                attrs={
                    'rows': 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hazard_types'].help_text = ''  # 'Click to select all hazards which apply to this specimen.'
        self.fields['description'].help_text = 'Please provide more details.'
        self.fields['description'].required = True

        self.body.append(
            Div(
                Div(
                    FieldWithButtons(
                        Field('name', required=True, css_class='form-control'),
                        StrictButton(
                            '<i class="bi-search"></i>', name='search', value='', id="search-compound",
                            css_class="btn-outline", title="Search in hazardous substances database ..."
                        ),
                    ),
                    css_class='col-sm-6'
                ),
                Div('source', css_class='col-sm-6'),
                css_class="row"
            ),
            Div(
                Div(Field('kind', css_class="selectize"), css_class='col-sm-6'),
                Div(Field('state', css_class="selectize"), css_class='col-sm-6'),
                Div(InlineCheckboxes('hazard_types'), css_class='col-xs-12 field-w3'),
                Div('description', css_class='col-sm-12'),
                css_class="row"
            ),
            Field('owner'),
            Field('hazards'),
        )

    def clean(self):
        data = super().clean()
        for pict in data.get('hazard_types', []):
            if pict.hazards.count() == 1:
                data['hazards'] |= pict.hazards.all()
        if data.get('state') == 'sealed':
            data['hazards'] |= models.Hazard
        print(data)
        return data

