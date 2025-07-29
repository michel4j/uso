from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse_lazy
from django.utils import timesince
from django.views.generic import edit
from itemlist.views import ItemListView

from misc.middleware import get_client_address
from django.conf import settings
from roleperms.views import RolePermsViewMixin
from . import forms
from . import models

USO_ADMIN_ROLES = getattr(settings, 'USO_ADMIN_ROLES', ["admin:uso"])
USO_CONTRACTS_ROLES = getattr(settings, 'USO_CONTRACTS_ROLES', ["contracts-admin"])


def dt_display(val, obj=None):
    return f'{timesince.timesince(val)} ago'


class AgreementList(RolePermsViewMixin, ItemListView):
    model = models.Agreement
    template_name = "item-list.html"
    list_title = "Agreements"
    allowed_roles = USO_ADMIN_ROLES + USO_CONTRACTS_ROLES
    list_columns = ["name", "code", "state", "num_users"]
    list_filters = ["state", "modified", "created"]
    list_transforms = {'created': dt_display, 'modified': dt_display}
    link_url = "edit-agreement"
    add_url = "add-agreement"
    link_search = ["name", "content", "description"]
    ordering = ["-state", "created", "modified"]


class AgreementFormMixin:
    template_name = "form.html"
    form_class = forms.AgreementForm
    success_url = reverse_lazy("agreement-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs


class CreateAgreement(RolePermsViewMixin, AgreementFormMixin, edit.CreateView):
    allowed_roles = USO_ADMIN_ROLES + USO_CONTRACTS_ROLES


class EditAgreement(RolePermsViewMixin, AgreementFormMixin, edit.UpdateView):
    queryset = models.Agreement.objects.all()
    allowed_roles = USO_ADMIN_ROLES + USO_CONTRACTS_ROLES

    def form_valid(self, form):
        if self.request.POST.get('submit') == "save-new":
            data = form.cleaned_data
            data['state'] = models.Agreement.STATES.disabled
            obj = models.Agreement.objects.create(**data)
            messages.success(self.request, 'New Agreement has been been created')
            response = HttpResponseRedirect(self.get_success_url())
        elif self.request.POST.get('submit') == "delete":
            obj = self.get_object()
            obj_repr = f'{obj}'
            if obj.state == models.Agreement.STATES.disabled:
                obj.delete()
                messages.success(self.request, f'Agreement {obj_repr} has been deleted')
            else:
                messages.error(
                    self.request,
                    f'Active agreement {obj_repr} can not be deleted. Must be disabled or archived'
                )
            response = HttpResponseRedirect(self.get_success_url())
        else:
            response = super().form_valid(form)
            messages.success(self.request, 'Agreement has been saved')
        return response


class AcceptAgreement(RolePermsViewMixin, edit.CreateView):
    model = models.Acceptance
    template_name = "form.html"
    form_class = forms.AcceptanceForm
    success_url = reverse_lazy("user-dashboard")

    def get_agreement(self):
        try:
            agreement = models.Agreement.objects.filter(state="enabled").get(code=self.kwargs['code'])
        except (models.Agreement.DoesNotExist, ValidationError):
            messages.error(self.request, "Invalid Agreement!")
            raise Http404("Agreement not found")
        return agreement

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['agreement'] = self.get_agreement()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["agreement"] = self.get_agreement()
        return context

    def form_valid(self, form):
        if form.cleaned_data.get("agreed"):
            ip_num = get_client_address(self.request)
            if ip_num == '254.254.254.254':
                messages.error(
                    self.request,
                    "Your acceptance was rejected because your computer could not be identified!"
                )
            else:
                agreement = self.get_agreement()
                data = {
                    "user": self.request.user,
                    "agreement_id": agreement.pk,
                    "host": ip_num
                }
                self.model.objects.create(**data)
                messages.success(self.request, "You have successfully accepted the agreement.")
        return HttpResponseRedirect(self.success_url)
