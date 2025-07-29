from misc.blocktypes import BaseBlock, BLOCK_TYPES


class AgreementBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "agreements/blocks/agreements.html"
    priority = 1

    def get_context_data(self):
        ctx = super().get_context_data()
        from agreements import models
        user = self.request.user
        self.visible = False

        if user.institution and user.institution.state == user.institution.STATES.exempt:
            return ctx

        if not user.institution:
            ctx['no_institution'] = True
            ctx['style_classes'] = 'bg-warning-subtle'
            self.visible = True
        elif user.institution.state == user.institution.STATES.new:
            ctx['request_contact'] = True
            ctx['style_classes'] = 'bg-warning-subtle'
            self.visible = True
        elif user.institution.state == user.institution.STATES.active:
            agreements = models.Agreement.objects.pending_for_user(user)
            if agreements.exists():
                ctx['style_classes'] = 'bg-primary-subtle'
                ctx["agreements"] = agreements
                self.visible = True

        return ctx
