from django import forms
from dynforms.forms import DynModelForm
from surveys.models import Feedback


class FeedbackForm(DynModelForm):
    class Meta:
        model = Feedback
        fields = ['cycle', 'beamline']

    def clean(self):
        cleaned_data = super().clean()
        details = cleaned_data['details']
        try:
            details['cycle_id'] = int(details['cycle'])
        except (ValueError, TypeError, KeyError):
            raise forms.ValidationError('Invalid cycle.')

        try:
            cleaned_data['beamline_id'] = int(details.get('facility'))
        except (ValueError, TypeError, KeyError):
            raise forms.ValidationError('Invalid beamline.')

        return cleaned_data


