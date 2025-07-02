from crispy_forms.bootstrap import StrictButton, FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, HTML, Field
from django import forms

from users import utils
from . import models


class AgreementForm(forms.ModelForm):
    roles = forms.MultipleChoiceField(label='Required for Roles', required=True)

    class Meta:
        model = models.Agreement
        fields = ("name", "state", "description", "roles", "content")
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 2,
                }
            ),
            "content": forms.Textarea(
                attrs={
                    "rows": 10,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.title = "Edit Agreement" if kwargs.get("instance") else "Create Agreement"
        self.helper.form_action = self.request.get_full_path()
        self.fields['roles'].choices = utils.uso_role_choices()
        left_buttons = Div(css_class="d-flex flex-row gap-3")
        right_buttons = Div(css_class="d-flex flex-row gap-3 ms-auto")
        buttons = FormActions(
            HTML("<hr/>"),
            Div(
                left_buttons,
                right_buttons,
                css_class="col-12 d-flex flex-row justify-content-between align-items-center"
            ),
            css_class="row"
        )
        if kwargs.get('instance'):
            if self.instance.state != models.Agreement.STATES.enabled:
                left_buttons.append(
                    StrictButton("Delete", type="submit", name="submit", value="delete", css_class="btn btn-danger")
                )
            right_buttons.append(
                StrictButton(
                    "Save as New", type="submit", name="submit", value="save-new", css_class="btn btn-secondary"
                )
            )
        right_buttons.append(
            StrictButton("Save ", type="submit", name="submit", value="save", css_class="btn btn-primary")
        )

        self.helper.layout = Layout(
            Div(
                Div("name", css_class="col-sm-12"),
                Div("state", css_class="col-sm-3"),
                Div("roles", title="Users with these roles must accept the agreement.", css_class="col-sm-9"),
                Div("description", css_class="col-sm-12"),
                Div(Field("content", css_class="rich-text-input"), css_class="col-sm-12"),
                css_class="row"
            ),
            buttons
        )


class AcceptanceForm(forms.ModelForm):
    agreed = forms.BooleanField(
        label="I acknowledge I have read and understood the terms of the agreement and "
              "affirm my agreement by submitting this form. I also acknowledge that I will need to reaffirm my agreement "
              "upon any substantial change to my affiliations"
    )

    class Meta:
        model = models.Acceptance
        fields = ("agreed",)

    def __init__(self, *args, **kwargs):
        self.agreement = kwargs.pop("agreement")
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.title = self.agreement.name
        self.helper.layout = Layout(
            Div(
                Div(
                    HTML("{% include 'agreements/detail.html' %}"),
                    css_class="col-xs-12"
                ),
                Div(
                    Field("agreed"),
                    css_class="col-xs-12"
                ),
                css_class="row"
            ),
            FormActions(
                HTML("<hr/>"),
                Div(
                    StrictButton("Submit", type="submit", value="Submit", css_class="btn btn-primary"),
                    css_class="pull-right"
                ),
            ),
        )
