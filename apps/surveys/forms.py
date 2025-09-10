from django import forms
from dynforms.forms import DynModelForm

from proposals.dynfields import ReviewCycle
from surveys.models import Feedback


class FeedbackForm(DynModelForm):
    class Meta:
        model = Feedback
        fields = ['cycle']

    def clean(self):
        from beamlines.models import Facility
        from proposals.models import ReviewCycle
        cleaned_data = super().clean()
        details = cleaned_data['details']
        try:
            details['cycle_id'] = int(details['cycle'])
        except (ValueError, TypeError, KeyError):
            raise forms.ValidationError('Invalid cycle.')

        try:
            cleaned_data['beamline_id'] = int(details['facility'])
        except (ValueError, TypeError, KeyError):
            raise forms.ValidationError('Invalid beamline.')
        return cleaned_data


