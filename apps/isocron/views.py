from django.conf import settings
from django.http import JsonResponse
from django.utils.safestring import mark_safe
from django.views import View
from django.views.generic import DetailView

from itemlist.views import ItemListView
from roleperms.views import RolePermsViewMixin
from . import models


USO_ADMIN_ROLES = getattr(settings, 'USO_ADMIN_ROLES', [])


def _format_state(value, obj=None):
    """
    Format the state of the task for display.
    """
    if value == models.TaskLog.StateType.running:
        return mark_safe("<span class='badge bg-info'>Running</span>")
    elif value == models.TaskLog.StateType.success:
        return mark_safe("<span class='badge bg-success'>Success</span>")
    elif value == models.TaskLog.StateType.failed:
        return mark_safe("<span class='badge bg-danger'>Failed</span>")
    else:
        return mark_safe("<span class='badge bg-secondary'>Never Ran</span>")


class TaskList(RolePermsViewMixin, ItemListView):
    model = models.BackgroundTask
    template_name = "item-list.html"
    paginate_by = 20
    list_columns = ['label', 'app', 'run_every', 'run_at', 'retry_after', 'last_ran', 'last_state', 'next_run', 'is_due']
    list_filters = ['created', 'modified']
    link_url = "task-detail"
    link_attr = 'data-modal-url'
    list_search = ['name', 'description', 'logs__message']    # Adjust based on your model fields
    ordering = ['label']
    required_roles = USO_ADMIN_ROLES
    list_transforms = {
        'last_state': _format_state,
    }


class TaskDetail(RolePermsViewMixin, DetailView):
    model = models.BackgroundTask
    template_name = "isocron/task-detail.html"
    context_object_name = 'task'
    required_roles = USO_ADMIN_ROLES


class RunTask(RolePermsViewMixin, View):
    model = models.BackgroundTask
    required_roles = USO_ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        task = self.model.objects.get(pk=kwargs['pk'])
        task.run_job(force=True)
        last_job = task.last_log()
        message = f"Task {task.name} completed: {last_job.get_state_display()}!"
        return JsonResponse({"url": ".", "message": message})

