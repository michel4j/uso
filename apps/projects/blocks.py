import copy

from django.db.models import Q

from misc.blocktypes import BaseBlock, BLOCK_TYPES


class ProjectsBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "projects/blocks/projects.html"
    priority = 4

    def get_context_data(self):
        ctx = super().get_context_data()
        from projects import models
        user = self.request.user
        projects = models.Project.objects.filter(team=user).distinct().order_by('-end_date')[:10]

        if not projects:
            self.visible = False

        ctx["projects"] = projects
        allocations = []
        for project in projects:
            allocations.extend(list(project.beamline_allocations().items()))
        ctx['beamlines'] = [(bl, alloc) for bl, alloc in allocations if alloc['can_renew']]

        return ctx
