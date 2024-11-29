import copy

from misc.blocktypes import BaseBlock, BLOCK_TYPES


class AgreementBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "agreements/blocks/agreements.html"
    priority = 1

    def render(self, context):
        ctx = copy.copy(context)
        from agreements import models
        user = context['request'].user
        show_block = False

        if user.institution and user.institution.state == user.institution.STATES.exempt:
            return None

        if not user.institution:
            ctx.update(
                {
                    'no_institution': True,
                }
            )
            show_block = True
        elif user.institution.state == user.institution.STATES.new:
            ctx.update(
                {
                    'request_contact': True,
                }
            )
            show_block = True
        elif user.institution.state == user.institution.STATES.active:
            agreements = models.Agreement.objects.pending_for_user(user)
            if agreements.exists():
                ctx.update(
                    {
                        "agreements": agreements
                    }
                )
                show_block = True

        if not show_block:
            return None

        return super().render(ctx)
