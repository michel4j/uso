import copy
from misc.blocktypes import BaseBlock, BLOCK_TYPES


class ActivityBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "misc/blocks/activity.html"
    priority = 99

    def render(self, context):
        ctx = copy.copy(context)
        from misc import models
        logs = models.ActivityLog.objects.filter(user=context['request'].user)
        if logs.exists():
            ctx.update({
                "logs": logs.order_by('-created')[:5],
            })
            return super().render(ctx)
        return ""
