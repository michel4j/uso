from django import forms

from dynforms.forms import  DynModelForm
from surveys.models import Feedback


class FeedbackForm(DynModelForm):
    type_code = 'feedback'

    class Meta:
        model = Feedback
        fields = []




