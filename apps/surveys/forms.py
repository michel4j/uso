
from dynforms.forms import DynModelForm
from surveys.models import Feedback


class FeedbackForm(DynModelForm):
    class Meta:
        model = Feedback
        fields = []




