from crisp_modals.views import ModalCreateView, ModalUpdateView, ModalDeleteView, ModalConfirmView
from django.conf import settings
from django.contrib.messages.views import SuccessMessageMixin
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from itemlist.views import ItemListView

from misc.utils import is_ajax
from roleperms.views import RolePermsViewMixin
from . import models, forms

USO_ADMIN_ROLES = getattr(settings, 'USO_ADMIN_ROLES', ["admin:uso"])


class UserNotificationDetail(RolePermsViewMixin, ModalConfirmView):
    template_name = "notifier/note-detail.html"
    model = models.Notification
    success_url = "."

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.request.user.notifications.all()
        return super().get_queryset(*args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # set the state to read if it is sent
        self.queryset.filter(pk=obj.pk, state=models.Notification.STATES.sent).update(
            state=models.Notification.STATES.read, modified=timezone.now()
        )
        return obj

    def confirmed(self, *args, **kwargs):
        obj = self.get_object()
        # change the state to acknowledged if it is read
        self.model.objects.filter(pk=obj.pk, state=models.Notification.STATES.read).update(
            state=self.model.STATES.acknowledged, modified=timezone.now()
        )
        return super().confirmed(*args, **kwargs)


class NotificationDetail(RolePermsViewMixin, ModalUpdateView):
    template_name = "notifier/admin-note-detail.html"
    model = models.Notification
    form_class = forms.UpdateNotificationForm

    def form_valid(self, *args, **kwargs):
        response = super().form_valid(*args, **kwargs)
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
    link_url = "user-notification-detail"
    link_attr = 'data-modal-url'
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
    link_url = "notification-detail"
    link_attr = 'data-modal-url'
    list_search = ['kind', 'data', 'user__first_name', 'user__last_name', 'emails']
    ordering = ['-created']
    allowed_roles = USO_ADMIN_ROLES


class MessageTemplateList(RolePermsViewMixin, ItemListView):
    model = models.MessageTemplate
    template_name = "notifier/notifier-list.html"
    paginate_by = 20
    list_columns = ['name', 'description', 'active', 'created', 'modified']
    list_filters = ['created', 'modified', 'kind', 'active']
    link_url = "edit-template-modal"
    link_attr = 'data-modal-url'
    list_search = ['name', 'description']
    ordering = ['-modified']
    allowed_roles = USO_ADMIN_ROLES


class CreateTemplate(SuccessMessageMixin, RolePermsViewMixin, ModalCreateView):
    form_class = forms.MessageTemplateForm
    model = models.MessageTemplate
    success_url = reverse_lazy('template-list')
    success_message = "Message Template '%(name)s' has been created."
    allowed_roles = USO_ADMIN_ROLES

    def form_valid(self, form):
        response = super().form_valid(form)
        if is_ajax(self.request):
            return JsonResponse({
                'pk': self.object.pk,
                'name': str(self.object),
            })
        else:
            return response


class EditTemplate(SuccessMessageMixin, RolePermsViewMixin, ModalUpdateView):
    form_class = forms.MessageTemplateForm
    model = models.MessageTemplate
    success_url = reverse_lazy('template-list')
    success_message = "Message Template '%(name)s' has been updated."
    allowed_roles = USO_ADMIN_ROLES

    def get_delete_url(self):
        return reverse_lazy('delete-template-modal', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        if is_ajax(self.request):
            return JsonResponse({
                'pk': self.object.pk,
                'name': str(self.object),
            })
        else:
            return response


class DeleteTemplate(RolePermsViewMixin, ModalDeleteView):
    model = models.MessageTemplate
