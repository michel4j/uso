from django.contrib import messages
from django.contrib.admin.utils import NestedObjects
from django.contrib.messages.views import SuccessMessageMixin
from django.db import DEFAULT_DB_ALIAS
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.text import capfirst
from django.views.generic import CreateView, UpdateView

from misc.utils import is_ajax
from . import models, forms
from misc.views import ConfirmDetailView
from itemlist.views import ItemListView
from roleperms.views import RolePermsViewMixin


class UserNotificationDetail(RolePermsViewMixin, ConfirmDetailView):
    template_name = "notifier/note-detail.html"
    model = models.Notification

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.request.user.notifications.all()
        return super().get_queryset(*args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        self.queryset.filter(pk=obj.pk, state=models.Notification.STATES.sent).update(
            state=models.Notification.STATES.read, modified=timezone.now()
        )
        return obj

    def get_success_url(self):
        return "."

    def confirmed(self, *args, **kwargs):
        obj = self.get_object()
        self.model.objects.filter(pk=obj.pk, state=models.Notification.STATES.read).update(
            state=self.model.STATES.acknowledged, modified=timezone.now()
        )
        return JsonResponse({"url": self.get_success_url()})


class NotificationDetail(RolePermsViewMixin, ConfirmDetailView):
    template_name = "notifier/admin-note-detail.html"
    model = models.Notification

    def confirmed(self, *args, **kwargs):
        obj = self.get_object()
        obj.state = obj.STATES.queued
        obj.deliver()
        return JsonResponse({"url": ""})


class UserNotificationList(RolePermsViewMixin, ItemListView):
    model = models.Notification
    template_name = "item-list.html"
    paginate_by = 20
    list_columns = ['kind', 'level', 'state', 'created', 'modified']
    list_filters = ['created', 'modified', 'level', 'state']
    link_url = "notification-detail"
    link_attr = 'data-url'
    list_search = ['kind', 'data']
    order_by = ['-created']

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.request.user.notifications.all()
        return super().get_queryset(*args, **kwargs)


class NotificationList(RolePermsViewMixin, ItemListView):
    model = models.Notification
    template_name = "item-list.html"
    paginate_by = 20
    list_columns = ['to', 'kind', 'created', 'modified']
    list_filters = ['created', 'modified', 'level', 'kind', 'state']
    link_url = "notification-admin-detail"
    link_attr = 'data-url'
    list_search = ['kind', 'data', 'user__first_name', 'user__last_name', 'emails']
    ordering = ['-created']
    allowed_roles = ['administrator:uso']


class MessageTemplateList(RolePermsViewMixin, ItemListView):
    model = models.MessageTemplate
    template_name = "notifier/notifier-list.html"
    paginate_by = 20
    list_columns = ['name', 'description', 'active', 'created', 'modified']
    list_filters = ['created', 'modified', 'kind', 'active']
    link_url = "edit-template-modal"
    link_attr = 'data-url'
    list_search = ['name', 'description']
    ordering = ['-modified']
    allowed_roles = ['administrator:uso']


class CreateTemplate(SuccessMessageMixin, RolePermsViewMixin, CreateView):
    form_class = forms.MessageTemplateForm
    template_name = "forms/modal.html"
    model = models.MessageTemplate
    success_url = reverse_lazy('template-list')
    success_message = "Message Template '%(name)s' has been created."
    allowed_roles = ['administrator:uso']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['submit_url'] = reverse_lazy('add-template-modal')
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(request=self.request)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        if is_ajax(self.request):
            return JsonResponse({
                'pk': self.object.pk,
                'name': str(self.object),
            })
        else:
            return response


class EditTemplate(SuccessMessageMixin, RolePermsViewMixin, UpdateView):
    form_class = forms.MessageTemplateForm
    template_name = "forms/modal.html"
    model = models.MessageTemplate
    success_url = reverse_lazy('template-list')
    success_message = "Message Template '%(name)s' has been updated."
    allowed_roles = ['administrator:uso']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(request=self.request)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['submit_url'] = reverse_lazy('edit-template-modal', kwargs={'pk': self.object.pk})
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if is_ajax(self.request):
            return JsonResponse({
                'pk': self.object.pk,
                'name': str(self.object),
            })
        else:
            return response


class DeleteTemplate(RolePermsViewMixin, ConfirmDetailView):
    model = models.MessageTemplate
    template_name = "forms/delete.html"

    def get_success_url(self):
        return reverse('template-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        collector = NestedObjects(using=DEFAULT_DB_ALIAS)  # database name
        collector.collect([context['object']])  # list of objects. single one won't do
        context['related'] = collector.nested(lambda x: '{}: {}'.format(capfirst(x._meta.verbose_name), x))
        return context

    def confirmed(self, *args, **kwargs):
        obj = self.get_object()
        msg = f'Message Template "{obj}" deleted'
        obj.delete()
        messages.success(self.request, msg)
        return JsonResponse({"url": self.get_success_url()})
