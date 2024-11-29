from django import template
from proposals import stats

register = template.Library()


@register.simple_tag(takes_context=True)
def get_stats_tables(context):
    return stats.get_proposal_stats()
