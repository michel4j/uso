

from django import template

from misc import blocktypes

blocktypes.autodiscover()

register = template.Library()


@register.inclusion_tag('users/dashboard.html', takes_context=True)
def show_dashboard(context):
    blocks = [
        block(context) for block in
        blocktypes.BaseBlock.get_plugins(blocktypes.BLOCK_TYPES.dashboard)
    ]
    return {
        'blocks': blocks,
    }
