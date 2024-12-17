from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, HTML, Field
from django import forms

from . import models


class Fieldset(Div):
    def __init__(self, title, *args, **kwargs):
        if 'css_class' not in kwargs:
            kwargs['css_class'] = "row narrow-gutter"
        super().__init__(
            Div(HTML("<h3>{}</h3><hr class='hr-xs'/>".format(title)), css_class="col-xs-12"),
            *args,
            **kwargs
        )


class ClarificationForm(forms.ModelForm):
    class Meta:
        model = models.Clarification
        fields = ['requester', 'question', 'content_type', 'object_id']
        widgets = {
            'requester': forms.HiddenInput(),
            'object_id': forms.HiddenInput(),
            'content_type': forms.HiddenInput(),
            'question': forms.Textarea(attrs={'rows': 5})
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.title = 'Request Clarification'
        self.helper.form_action = self.request.get_full_path()
        self.helper.layout = Layout(
            Div(
                Div(
                    'requester', 'content_type', 'object_id',
                    Div('question', css_class="col-xs-12"),
                    css_class="col-xs-12 narrow-gutter"
                ),
                css_class="row"
            ),
            Div(
                Div(
                    Div(
                        StrictButton('Submit', type='submit', value='Save',
                                     css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            )
        )


class ResponseForm(forms.ModelForm):
    class Meta:
        model = models.Clarification
        fields = ['response', 'responder']
        widgets = {
            'response': forms.Textarea(attrs={'rows': 5}),
            'responder': forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.title = 'Clarification Response'
        self.helper.form_action = self.request.get_full_path()
        self.helper.layout = Layout(
            Div(
                Div(
                    Div(HTML(
                        '<h4>{0}</h4><hr/><span>{1}</span>'.format(self.instance.reference,
                                                                    self.instance.question)),
                        css_class="tinytron"),
                    Div('response', css_class="col-xs-12"),
                    css_class="col-xs-12 narrow-gutter"
                ),
                css_class="row"
            ),
            'responder',
            Div(
                Div(
                    Div(
                        StrictButton('Submit', type='submit', value='Submit',
                                     css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            )
        )


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = models.Attachment
        fields = ('owner', 'content_type', 'object_id', 'file', 'description', 'kind')
        widgets = {
            'content_type': forms.HiddenInput,
            'object_id': forms.HiddenInput,
            'owner': forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_action = self.request.get_full_path()
        self.helper.title = "Manage Attachments"
        self.helper.layout = Layout(
            Div(
                Div(
                    Div(Field('kind', css_class="chosen"), css_class="col-xs-2"),
                    Div('description', css_class="col-xs-3"),
                    Div(Field('file', template="%s/file_input.html"), css_class="col-xs-7"),
                    Field('owner'), Field('object_id'), Field('content_type'),
                    css_class="row narrow-gutter"
                ),
            )
        )
