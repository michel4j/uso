from django.conf import settings
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse
from dynforms.models import FormType
from dynforms.views import DynCreateView

from roleperms.views import RolePermsViewMixin
from . import forms
from .models import Feedback

USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ["admin:uso"])


class UserFeedback(RolePermsViewMixin, DynCreateView):
    form_class = forms.FeedbackForm
    model = Feedback
    template_name = "surveys/survey-form.html"

    def get_initial(self):
        initial = super().get_initial()
        return initial

    def get_form_type(self) -> FormType:
        form_type = FormType.objects.filter(code="feedback").first()
        if not form_type:
            raise Http404("Form type not found.")
        return form_type

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = "User Feedback"
        return context

    def get_success_url(self):
        success_url = reverse("user-dashboard")
        return success_url

    def form_valid(self, form):
        data = form.cleaned_data
        obj = self.model(**data)
        obj.save()
        return HttpResponseRedirect(self.get_success_url())
