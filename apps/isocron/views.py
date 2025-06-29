from django.conf import settings
from django.views.generic import DetailView

from itemlist.views import ItemListView
from roleperms.views import RolePermsViewMixin
from . import models


USO_ADMIN_ROLES = getattr(settings, 'USO_ADMIN_ROLES', [])


class TaskList(RolePermsViewMixin, ItemListView):
    model = models.BackgroundTask
    template_name = "item-list.html"
    paginate_by = 20
    list_columns = ['task', 'app', 'run_every', 'run_at', 'retry_after', 'keep_logs', 'last_ran', 'next_run', 'is_due']
    list_filters = ['created', 'modified']
    link_url = "task-detail"
    link_attr = 'data-modal-url'
    list_search = ['name', 'description', 'logs__message']    # Adjust based on your model fields
    order_by = ['-modified']
    required_roles = USO_ADMIN_ROLES


class TaskDetail(RolePermsViewMixin, DetailView):
    model = models.BackgroundTask
    template_name = "isocron/task-detail.html"
    context_object_name = 'task'
    required_roles = USO_ADMIN_ROLES


