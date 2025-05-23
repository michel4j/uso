from django import forms

from dynforms.forms import DynFormMixin
from projects.models import Project
from surveys.models import Feedback


class FeedbackForm(DynFormMixin, forms.ModelForm):
    type_code = 'feedback'

    class Meta:
        model = Feedback
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.init_fields()

    def _custom_clean(self, data):
        data['active_page'] = '1'
        return super()._custom_clean(data)


