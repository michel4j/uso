from crisp_modals.views import ModalCreateView, ModalUpdateView
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseRedirect, JsonResponse
from django.utils import timezone
from django.views.generic import edit, View
from django.conf import settings
from . import forms
from . import models
from roleperms.views import RolePermsViewMixin
from .utils import is_ajax
from django.shortcuts import render

USO_ADMIN_ROLES = getattr(settings, 'USO_ADMIN_ROLES', ["admin:uso"])


class JSONResponseMixin(object):
    def render_to_response(self, context):
        "Returns a JSON response containing 'context' as payload"
        return JsonResponse(context, safe=False)


class ConfirmDetailView(edit.DeleteView):
    """derived from edit.DeleteView to re-use the same get-confirm-post-execute pattern
    Sub-classes should implement 'confirmed' method
    """

    def form_valid(self, form):
        return self.confirmed(self)

    def delete(self, *args, **kwargs):
        return self.confirmed(self, *args, **kwargs)

    def confirmed(self, *args, **kwargs):
        return HttpResponseRedirect(self.get_success_url())


class ManageAttachments(RolePermsViewMixin, ModalCreateView):
    template_name = "misc/attachments.html"
    model = models.Attachment
    reference_model = None
    form_class = forms.AttachmentForm
    admin_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        return self.request.get_full_path()

    def get_reference(self, queryset=None):
        if self.reference_model:
            self.reference = self.reference_model.objects.get(pk=self.kwargs.get('pk'))
            return self.reference
        else:
            raise ValueError('Reference Model Not Provided')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reference'] = self.reference
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
        kwargs['request'] = self.request
        return kwargs


class DeleteAttachment(RolePermsViewMixin, edit.DeleteView):
    model = models.Attachment
    admin_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        obj = self.get_object()
        return (obj.owner == self.request.user and obj.is_editable) or self.check_admin()

    def get_object(self, **kwargs):
        self.object = models.Attachment.objects.get(owner=self.request.user, slug=self.kwargs['slug'])
        return self.object

    def get_success_url(self):
        return self.request.GET.get('next', '/')

    def delete(self, *args, **kwargs):
        obj = self.get_object()
        if hasattr(obj.reference, "is_editable") and obj.reference.is_editable():
            obj.delete()
        return HttpResponseRedirect(self.get_success_url())


class RequestClarification(RolePermsViewMixin, ModalCreateView):
    form_class = forms.ClarificationForm
    model = models.Clarification
    reference_model = None

    def get_success_url(self):
        return self.request.get_full_path()

    def get_reference(self, queryset=None):
        if self.reference_model:
            self.reference = self.reference_model.objects.get(pk=self.kwargs.get('pk'))
            return self.reference
        else:
            raise ValueError('Reference Model Not Provided')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        reference = self.get_reference()
        initial['requester'] = self.request.user
        initial['content_type'] = ContentType.objects.get_for_model(reference)
        initial['object_id'] = reference.pk
        return initial

    def form_valid(self, form):
        super().form_valid(form)
        return JsonResponse({
            "url": None
        })


class ClarificationResponse(RolePermsViewMixin, ModalUpdateView):
    form_class = forms.ResponseForm
    model = models.Clarification
    reference_model = None

    def get_reference(self, queryset=None):
        if self.reference_model:
            self.reference = self.reference_model.objects.get(pk=self.kwargs.get('ref'))
            return self.reference
        else:
            raise ValueError('Reference Model Not Provided')

    def get_success_url(self):
        return self.request.get_full_path()

    def get_initial(self):
        initial = super().get_initial()
        initial['responder'] = self.request.user
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        super().form_valid(form)
        return JsonResponse({
            "url": ""
        })


class Ping(RolePermsViewMixin, View):
    def get(self, request):
        return JsonResponse({
            'server_time': timezone.localtime(timezone.now()).isoformat()
        })
