from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, HTML
from django import forms
from django.utils.translation import gettext as _

from misc.forms import Fieldset
from . import models


class FacilityForm(forms.ModelForm):
    time_staff = forms.IntegerField(label=_('Staff (%)'), min_value=0, max_value=100, required=False)
    time_maintenance = forms.IntegerField(label=_('Maintenance (%)'), min_value=0, max_value=100, required=False)
    time_beamteam = forms.IntegerField(label=_('Beam Team (%)'), min_value=0, max_value=100, required=False)
    time_purchased = forms.IntegerField(label=_('Purchased (%)'), min_value=0, max_value=100, required=False)
    time_user = forms.IntegerField(
        label=_('User (%)'), min_value=0, max_value=100, required=False,
        widget=forms.NumberInput(attrs={'readonly': True})
    )
    public_support = forms.BooleanField(
        label=_('Make Staff Schedule Public'),
        required=False,
        widget=forms.Select(choices=((False, "No"), (True, "Yes")))
    )

    class Meta:
        model = models.Facility
        fields = ('name', 'kind', 'acronym', 'port', 'description', 'url', 'range', 'parent',
                  'state', 'spot_size', 'flux', 'resolution', 'source', 'flex_schedule',
                  'public_support', 'shift_size')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, }),
            'flex_schedule': forms.Select(choices=((True, "Yes"), (False, "No"))),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "facility-form"
        self.helper.title = "Create/Edit Facility Information"

        self.helper.layout = Layout(
            Div(
                Div('name', css_class="col-sm-8"),
                Div(Field('parent', css_class="chosen"), css_class="col-sm-4"),
                Div('acronym', css_class="col-sm-3"),
                Div(Field('kind', css_class="chosen"), css_class="col-sm-3"),
                Div(Field('url', placeholder="http:// ..."), css_class='col-sm-6'),
                Div('description', css_class='col-sm-12'),
                css_class="row narrow-gutter"
            ),
            Fieldset(
                "Parameters",
                Div('source', required=True, css_class="col-sm-5"),
                Div('port', css_class="col-sm-2"),
                Div(Field('state', css_class="chosen"), css_class="col-sm-5"),
                Div('range', required=True, css_class="col-sm-6"),
                Div('flux', required=True, css_class="col-sm-6"),
                Div('resolution', required=True, css_class="col-sm-6"),
                Div('spot_size', required=True, css_class="col-sm-6")
            ),

            Fieldset(
                "Beam Time Allocation",
                Div('time_staff', css_class="col-sm-2"),
                Div('time_maintenance', css_class="col-sm-3"),
                Div('time_beamteam', css_class="col-sm-2"),
                Div('time_purchased', css_class="col-sm-3"),
                Div('time_user', css_class="col-sm-2"),
                css_class="combine row narrow-gutter"
            ),
            Div(
                Div(Field('flex_schedule', css_class='chosen'), css_class="col-sm-4"),
                Div(Field('shift_size', css_class="chosen"), css_class="col-sm-4"),
                Div(Field('public_support', css_class="chosen"), css_class="col-sm-4"),
                css_class="row narrow-gutter"
            ),
            HTML("<hr class='hr-xs'/>"),
            Div(
                Div(
                    StrictButton('Revert', type='reset', value='Reset', css_class="btn btn-default"),
                    StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'),
                    css_class="col-xs-12"
                ),
                css_class="row"
            )
        )

    def clean(self):
        data = super().clean()
        data['details'] = {
            'beamtime': {
                k: data.pop('time_{}'.format(k)) for k in ['staff', 'maintenance', 'purchased', 'beamteam', 'user']
            },
            'public_support': data.pop('public_support', False)
        }
        data['acronym'] = data.get('acronym', '').upper().replace('_', '-').replace(' ', '').strip()
        return data
