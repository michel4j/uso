import uuid

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

CATEGORY_COLORS = ['#7eb852', '#07997e', '#4f54a8', '#991c71', '#cf003e', '#e3690b', '#efb605', '#a5a5a5']


@register.inclusion_tag('misc/plots/table_plot.html')
def render_plot(table, name=None, plot_type="multiBarChart"):
    if not name:
        name = uuid.uuid4().hex
    categories = [r[0] for r in table.table[1:]]
    color_scheme = dict(list(zip(categories, CATEGORY_COLORS)))
    data = table.plot_data(color_scheme=color_scheme)
    return {
        'table': table.html({'class': 'table table-hover'}),
        'name': name,
        'data': data,
        'types': list(color_scheme.keys()),
        'colors': list(color_scheme.values()),
        'plot_type': plot_type
    }


@register.simple_tag(takes_context=True)
def show_table(context, tbl):
    html = tbl.html({'class': 'table table-hover table-condensed'})
    return mark_safe(html)
