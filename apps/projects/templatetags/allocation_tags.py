from django import template

register = template.Library()


@register.filter
def discretionary_time(data):
    return data


@register.simple_tag
def allocation_style(allocation, cutoff, decision):
    if allocation.score == 0 or allocation.score > decision:
        return ''
    elif allocation.score <= cutoff:
        return 'bg-success-subtle'
    elif allocation.score <= decision:
        return 'bg-warning-subtle'
    else:
        return ''
