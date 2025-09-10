from django.conf import settings
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse
from django.views.generic import DetailView
from dynforms.models import FormType
from dynforms.views import DynCreateView
from itemlist.views import ItemListView

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
        data['user'] = self.request.user
        form_type = self.get_form_type()
        rating_fields = [
            field.name
            for page in form_type.get_pages() for field in page.fields
            if field.field_type == 'likert'
        ]

        # Extract ratings from details
        details = data.get('details', {})
        ratings = {key: details.pop(key) for key in rating_fields if key in details}
        data['details'] = details  # Update details without ratings

        # Create the Feedback object
        obj = self.model(**data)
        obj.save()

        # Create Rating objects
        from .models import Rating, Category
        new_ratings = []
        for key, items in ratings.items():
            try:
                category_name = key.replace('_', ' ').capitalize()
                category, _ = Category.objects.get_or_create(name=category_name)
                new_ratings.extend([
                    Rating(feedback=obj, category=category, **item)
                    for item in items
                ])
            except Exception as e:
                # Log the error, but continue processing other ratings
                print(f"Error saving rating {key}: {e}")
        Rating.objects.bulk_create(new_ratings)
        return HttpResponseRedirect(self.get_success_url())


class AdminFeedbackList(RolePermsViewMixin, ItemListView):
    model = Feedback
    template_name = "item-list.html"
    paginate_by = 25
    link_url = 'feedback-detail'
    link_attr = 'data-modal-url'
    list_columns = ['user', 'beamline', 'cycle', 'created']
    list_filters = ['beamline', 'cycle', 'created']
    ordering = ['-created']
    required_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES


class CycleFeedbackList(AdminFeedbackList):
    def get_queryset(self):
        self.queryset = self.model.objects.filter(cycle__pk=self.kwargs.get('cycle'))
        return super().get_queryset()


def _fmt_survey_details(details, obj):
    if not details:
        return ''
    parts = []
    if 'beamline' in details:
        parts.append(", ".join([f'{entry["name"]}: {entry["label"]}' for entry in details['beamline']]))
    return ", ".join(parts)


class FacilityFeedbackList(AdminFeedbackList):
    list_columns = ['details', 'cycle', 'created']
    list_filters = ['beamline', 'cycle', 'created']
    list_transforms = {
        'details': _fmt_survey_details,
    }

    def check_allowed(self):
        from beamlines.models import Facility
        facility = Facility.objects.get(acronym__iexact=self.kwargs.get('facility'))
        return facility.is_admin(self.request.user) or super().check_allowed()

    def get_list_title(self):
        return f"{self.kwargs.get('facility')} User Feedback"

    def get_queryset(self):
        self.queryset = self.model.objects.filter(beamline__acronym__iexact=self.kwargs.get('facility'))
        return super().get_queryset()


class FeedbackDetail(RolePermsViewMixin, DetailView):
    model = Feedback
    template_name = "surveys/feedback-detail.html"
    admin_roles = USO_ADMIN_ROLES
    required_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        feedback = self.get_object()
        if feedback.beamline:
            is_facility_admin =feedback.beamline.is_admin(self.request.user)
        else:
            is_facility_admin = False
        return (
                super().check_allowed() or
                self.check_admin() or
                is_facility_admin
        )
