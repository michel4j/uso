
from crispy_forms.bootstrap import  StrictButton, FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div,  HTML
from django import forms
from django.urls import reverse_lazy

from . import models


class MessageTemplateForm(forms.ModelForm):
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

        self.helper = FormHelper()
        if kwargs.get('instance'):
            self.helper.title = 'Edit Message Template'
            self.helper.form_action = self.request.get_full_path()
            delete_url = f"{reverse_lazy('delete-template-modal', kwargs={'pk': self.instance.pk})}"

            buttons = FormActions(
                HTML("<hr/>"), StrictButton(
                    'Delete', id="delete-object", css_class="btn btn-danger", data_url=delete_url
                ), Div(
                    StrictButton('Cancel', type='button', data_dismiss='modal', css_class="btn btn-default"),
                    StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'), css_class='pull-right'
                ),
            )

        else:
            self.helper.title = 'Create Message Template'
            self.helper.form_action = self.request.get_full_path()
            buttons = FormActions(
                HTML("<hr/>"), Div(
                    StrictButton('Revert', type='reset', value='Reset', css_class="btn btn-default"),
                    StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'), css_class='pull-right'
                ), )

        self.helper.layout = Layout(
            Div(
                Div('name', css_class='col-xs-12'),
                css_class="row narrow-gutter"
            ),
            Div(
                Div("description", css_class='col-xs-12'),
                Div("content", css_class='col-xs-12'),
                Div('active', css_class='col-xs-12'),
                css_class="row narrow-gutter"
            ),
            Div(
                Div(
                    buttons, css_class="col-xs-12"
                ),
                css_class="row"
            )
        )

