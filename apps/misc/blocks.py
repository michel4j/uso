import copy
from misc.blocktypes import BaseBlock, BLOCK_TYPES


class ActivityBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "misc/blocks/activity.html"
    style_classes = "bg-warning-subtle"
    priority = 99

    def get_context_data(self):
        ctx = super().get_context_data()
        from misc import models
        logs = models.ActivityLog.objects.filter(user=self.request.user)
        if logs.exists():
            ctx["logs"] = logs.order_by('-created')[:5]
            return ctx
        return {}
