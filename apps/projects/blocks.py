import copy

from django.db.models import Q

from misc.blocktypes import BaseBlock, BLOCK_TYPES


class ProjectsBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "projects/blocks/projects.html"
    priority = 4

    def check_allowed(self, request):
        return request.user.is_authenticated

    def render(self, context):
        ctx = copy.copy(context)
        from projects import models
        user = context['request'].user

        filters = Q(leader=user) | Q(spokesperson=user) | Q(delegate=user)
        projects = models.Project.objects.filter(filters)

        ctx.update({
            "projects": projects
        })
        if not projects:
            return ""
        return super().render(ctx)
