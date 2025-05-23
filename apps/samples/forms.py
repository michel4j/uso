import json
import re

from crisp_modals.forms import ModalModelForm
from crispy_forms.bootstrap import FieldWithButtons, StrictButton, FormActions, InlineCheckboxes
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, HTML
from django import forms
from django.urls import reverse_lazy

from . import models
from .widgets import HazardSelectMultiple


class SampleForm(ModalModelForm):
    hazards = forms.CharField(required=False)

    class Meta:
        model = models.Sample
        fields = ('owner', 'name', 'source', 'kind', 'description', 'state', 'hazard_types', 'hazards')
        widgets = {'hazard_types': HazardSelectMultiple(),
                   'hazards': forms.HiddenInput(),
                   'description': forms.Textarea(
                       attrs={
                           'rows': 3,
                       }
                   ),
                   }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)
        self.fields['hazard_types'].help_text = ''  # 'Click to select all hazards which apply to this specimen.'
        self.fields['description'].help_text = 'Please provide more details.'
        self.fields['description'].required = True

        if kwargs.get('instance'):
            self.body.form_action = self.request.get_full_path()
            delete_url = f"{reverse_lazy('sample-delete', kwargs={'pk': self.instance.pk})}"

        self.body.append(
            Div(
                Div(
                    FieldWithButtons(
                        Field('name', required=True, css_class='form-control'),
                        StrictButton(
                            '<i class="bi-search"></i>', name='search', value='', id="search-compound",
                            css_class="btn-light border", title="Search in hazardous substances database ..."
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
            Field('owner', type="hidden"),
            Field('hazards', type="hidden"),
        )

    def clean(self):
        data = super().clean()
        for pict in data.get('hazard_types', []):
            if pict.hazards.count() == 1:
                data['hazards'] |= pict.hazards.all()
        if data.get('state') == 'sealed':
            data['hazards'] |= models.Hazard
        return data

    def clean_hazards(self):
        hazard_txt = re.sub(r'[^\d\]\[\s,]', '', self.cleaned_data['hazards'])
        hazard_pks = self.cleaned_data['hazards'] and json.loads(hazard_txt) or []
        return models.Hazard.objects.filter(pk__in=hazard_pks)
