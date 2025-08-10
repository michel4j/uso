from crisp_modals.views import ModalCreateView, ModalUpdateView
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse, Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View
from reportcraft.views import ReportIndexView, ReportData, DataView, ReportView

from roleperms.views import RolePermsViewMixin
from . import forms
from . import models

USO_ADMIN_ROLES = getattr(settings, 'USO_ADMIN_ROLES', ["admin:uso"])


class JSONResponseMixin(object):
    def render_to_response(self, context):
        "Returns a JSON response containing 'context' as payload"
        return JsonResponse(context, safe=False)


class ManageAttachments(RolePermsViewMixin, ModalCreateView):
    template_name = "misc/attachments.html"
    model = models.Attachment
    reference_model = None
    form_class = forms.AttachmentForm
    admin_roles = USO_ADMIN_ROLES

    def get_reference(self, queryset=None):
        if self.reference_model:
            return self.reference_model.objects.get(pk=self.kwargs.get('pk'))
        else:
            raise Http404('Reference Model Not Provided')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reference'] = self.get_reference()
        return context

    def get_initial(self):
        initial = super().get_initial()
        reference = self.get_reference()
        initial['owner'] = self.request.user
        initial['content_type'] = ContentType.objects.get_for_model(reference)
        initial['object_id'] = reference.pk
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        context = self.get_context_data()
        context['form'] = form
        return render(self.request, self.template_name, context)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['form_action'] = self.request.get_full_path()
        return kwargs


class DeleteAttachment(RolePermsViewMixin, View):
    model = models.Attachment
    admin_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        obj = self.get_object()
        return (obj.owner == self.request.user and obj.is_editable) or self.check_admin()

    def get_object(self, **kwargs):
        self.object = models.Attachment.objects.get(owner=self.request.user, slug=self.kwargs['slug'])
        return self.object

    def post(self, request, *args, **kwargs):
        if not self.check_allowed():
            return JsonResponse({"error": "You are not allowed to delete this attachment."}, status=403)

        obj = self.get_object()
        if hasattr(obj.reference, "is_editable") and obj.reference.is_editable() or self.check_admin():
            obj.delete()
            return JsonResponse({"success": True, "message": "Attachment deleted successfully."})
        else:
            return JsonResponse({"error": "Attachment cannot be deleted."}, status=400)


class RequestClarification(RolePermsViewMixin, ModalCreateView):
    form_class = forms.ClarificationForm
    model = models.Clarification
    reference_model = None

    def get_reference(self, queryset=None):
        if self.reference_model:
            return self.reference_model.objects.get(pk=self.kwargs.get('pk'))
        else:
            raise Http404('Reference Not Provided')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['form_action'] = self.request.get_full_path()
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        reference = self.get_reference()
        initial['requester'] = self.request.user
        initial['content_type'] = ContentType.objects.get_for_model(reference)
        initial['object_id'] = reference.pk
        return initial


class ClarificationResponse(RolePermsViewMixin, ModalUpdateView):
    form_class = forms.ResponseForm
    model = models.Clarification
    reference_model = None
    success_url = "."

    def get_reference(self, queryset=None):
        if self.reference_model:
            return self.reference_model.objects.get(pk=self.kwargs.get('ref'))
        else:
            raise Http404('Reference Model Not Provided')

    def get_initial(self):
        initial = super().get_initial()
        initial['responder'] = self.request.user
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['form_action'] = self.request.get_full_path()
        return kwargs


class Ping(RolePermsViewMixin, View):
    def get(self, request):
        return JsonResponse({
            'server_time': timezone.localtime(timezone.now()).isoformat()
        })


class SectionIndex(RolePermsViewMixin, ReportIndexView):
    """
    View to handle reporting a section of the site.
    """
    required_roles = USO_ADMIN_ROLES
    link_url = 'report-section-view'

    def get_link_url(self, obj):
        """
        Returns the URL for the section report.
        """
        return reverse(self.link_url, kwargs={'section': obj.section, 'slug': obj.slug})

    def get_limit_section(self):
        """
        Returns the section limit for the report.
        """
        return self.kwargs.get('section', 'general')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = self.get_limit_section().title()
        return context


class SectionData(RolePermsViewMixin, DataView):
    """
    View to handle admin reporting a section of the site.
    """

    required_roles = USO_ADMIN_ROLES

    def get_queryset(self):
        """
        Returns the queryset for the report.
        """
        section = self.kwargs.get('section', None)
        return super().get_queryset().filter(section=section)


class SectionReport(RolePermsViewMixin, ReportView):
    """
    View to handle reporting a section of the site.
    """
    template_name = 'misc/report-view.html'
    required_roles = USO_ADMIN_ROLES

    def get_queryset(self):
        """
        Returns the queryset for the report.
        """
        section = self.kwargs.get('section', None)
        return super().get_queryset().filter(section=section)

    def get_data_url(self):
        """
        Returns the section limit for the report.
        """
        section = self.kwargs.get('section', None)
        if section:
            return reverse('report-section-data', kwargs={'section': section, 'slug': self.kwargs.get('slug')})
        else:
            raise Http404("Section not specified or does not exist.")
