import copy

from misc.blocktypes import BaseBlock, BLOCK_TYPES


class ProfileBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "users/blocks/profile.html"
    priority = 0


class ActivityBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "users/blocks/activity.html"
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

# class UserMapBlock(BaseBlock):
#     block_type = BLOCK_TYPES.dashboard
#     template_name = "users/blocks/map.html"
#     priority = 4
#
#     def check_allowed(self, request):
#         if request.user.address:
#             return True
#
#     def render(self, context):
#         return super().render(context)
