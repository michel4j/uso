from crisp_modals.forms import ModalModelForm, FullWidth, Row
from crispy_forms.bootstrap import  StrictButton, FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div,  HTML
from django import forms
from django.urls import reverse_lazy

from . import models


class MessageTemplateForm(ModalModelForm):
    class Meta:
        model = models.MessageTemplate
        fields = ('name', 'description', 'content', 'active')
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Name or path of the message template.'}),
            'description': forms.TextInput(attrs={'placeholder': 'Please provide a brief description.'}),
            'content': forms.Textarea(
                attrs={'rows': 10, 'placeholder': 'Please provide the message content. use {{variable}} for dynamic content substitutions.'}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)

        self.body.form_action = self.request.get_full_path()
        self.body.append(
            Row(
                FullWidth('name'),
            ),
            Row(
                FullWidth("description"),
                FullWidth("content"),
                FullWidth('active'),
            ),
        )

class UpdateNotificationForm(ModalModelForm):
    class Meta:
        model = models.Notification
        fields = ()

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)
        self.body.form_action = self.request.get_full_path()
