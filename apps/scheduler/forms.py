from crisp_modals.forms import ModalModelForm
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
                Div('description', css_class="col-sm-6"),
                Div(Field('config', css_class="selectize"), css_class="col-sm-6"),
                Div(Field('start_date', readonly=True), css_class="col-sm-6"),
                Div(Field('end_date', readonly=True), css_class="col-sm-6"),
                css_class="row"
            ),
            Div(
                Div(
                    Div(
                        StrictButton("Cancel", type="button", css_class="btn btn-secondary pull-left",
                                     data_dismiss="modal"),
                        StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-sm-12"
                ),
                css_class="modal-footer row"
            )
        )


class ModeTypeForm(ModalModelForm):
    class Meta:
        model = models.ModeType
        fields = ['acronym', 'name', 'is_normal', 'active', 'description', 'color']
        widgets = {
            'color': forms.TextInput(attrs={'type': 'color'}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.body.append(
            Div(
                Div('acronym', css_class="col-sm-3"),
                Div('name', css_class="col-sm-7"),
                Div(Field('color', css_class="form-control form-control-color w-100"), css_class="col-sm-2"),
                Div('description', css_class="col-sm-12"),
                Div('is_normal', css_class="col-sm-6"),
                Div('active', css_class="col-sm-6"),
                css_class="row"
            )
        )


class ShiftConfigForm(ModalModelForm):
    class Meta:
        model = models.ShiftConfig
        fields = ['start', 'duration', 'number', 'names']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.body.append(
            Div(
                Div('start', css_class="col-sm-6"),
                Div('duration', css_class="col-sm-6"),
                Div('number', css_class="col-sm-6"),
                Div('names', css_class="col-sm-6"),
                css_class="row"
            )
        )