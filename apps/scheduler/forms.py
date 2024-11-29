from django import forms
from . import models
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field
from crispy_forms.bootstrap import StrictButton


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = models.Schedule
        fields = ['description', 'start_date', 'end_date', 'config']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.title = 'Add Schedule'
        self.helper.form_action = self.request.get_full_path()
        self.helper.layout = Layout(
            Div(
                Div('description', css_class="col-xs-6"),
                Div(Field('config', css_class="chosen"), css_class="col-xs-6"),
                Div(Field('start_date', readonly=True), css_class="col-xs-6"),
                Div(Field('end_date', readonly=True), css_class="col-xs-6"),
                css_class="row narrow-gutter"
            ),
            Div(
                Div(
                    Div(
                        StrictButton("Cancel", type="button", css_class="btn btn-default pull-left",
                                     data_dismiss="modal"),
                        StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            )
        )
