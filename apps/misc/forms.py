from crisp_modals.forms import ModalModelForm, FullWidth, Row, QuarterWidth, HalfWidth, ThirdWidth, TwoThirdWidth
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, HTML, Field
from django import forms

from . import models


class Fieldset(Div):
    def __init__(self, title, *args, **kwargs):
        if 'css_class' not in kwargs:
            kwargs['css_class'] = "row"
        super().__init__(
            Div(HTML("<h3>{}</h3><hr class='hr-xs'/>".format(title)), css_class="col-xs-12"),
            *args,
            **kwargs
        )


class ClarificationForm(ModalModelForm):
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
        super().__init__(*args, **kwargs)
        self.body.append(
            Row(
                FullWidth('question'),
                Field('requester'),
                Field('content_type'),
                Field('object_id'),
            ),
        )


class ResponseForm(ModalModelForm):
    class Meta:
        model = models.Clarification
        fields = ['response', 'responder']
        widgets = {
            'response': forms.Textarea(attrs={'rows': 5}),
            'responder': forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.body.append(
            Row(
                Div(
                    HTML(
                        f'<h4>{self.instance.reference}</h4><hr/><span>{self.instance.question}</span>'
                    ),
                    css_class="alert alert-info"
                ),
                FullWidth('response'),
            ),
            Field('responder'),
        )


class AttachmentForm(ModalModelForm):
    class Meta:
        model = models.Attachment
        fields = ('owner', 'content_type', 'object_id', 'file', 'description', 'kind')
        widgets = {
            'content_type': forms.HiddenInput,
            'object_id': forms.HiddenInput,
            'owner': forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.body.title = "Manage Attachments"
        self.body.append(
            Row(
                ThirdWidth('kind'),
                TwoThirdWidth('description'),
                FullWidth(Field('file', template="%s/file_input.html")),
                Field('owner'), Field('object_id'), Field('content_type'),
            ),
        )
        self.footer.layout = Layout(
            StrictButton('Close', css_class='btn btn-secondary', data_bs_dismiss="modal", aria_label="Close")
        )
