from django import template

from projects import stats

register = template.Library()


@register.simple_tag(takes_context=True)
def get_stats_tables(context):
    return stats.get_project_stats()
