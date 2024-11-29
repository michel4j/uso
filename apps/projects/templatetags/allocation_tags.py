from django import template

register = template.Library()


@register.filter(name="discretionary_time")
def discretionary_time(data):
    return data


@register.simple_tag(name='allocation_style')
def allocation_style(allocation, cutoff, decision):
    if allocation.score_merit == 0 or allocation.score_merit > decision:
        return ''
    elif allocation.score_merit <= cutoff:
        return 'alert-success'
    elif allocation.score_merit <= decision:
        return 'alert-warning'
    else:
        return ''
