import copy

from django import template

from misc import blocktypes

blocktypes.autodiscover()

register = template.Library()


@register.inclusion_tag('users/dashboard.html', takes_context=True)
def show_dashboard(context):
    ctx = copy.copy(context)
    blocks = blocktypes.BaseBlock.get_plugins(blocktypes.BLOCK_TYPES.dashboard)
    ctx.update({'blocks': blocks})
    return ctx
