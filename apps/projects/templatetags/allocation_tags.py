from django import template

register = template.Library()


@register.filter(name="discretionary_time")
def discretionary_time(data):
    return data


@register.simple_tag(name='allocation_style')
def allocation_style(allocation, cutoff, decision):
    print(allocation, cutoff, decision)
    if allocation.score == 0 or allocation.score > decision:
        return ''
    elif allocation.score <= cutoff:
        return 'alert-success'
    elif allocation.score <= decision:
        return 'alert-warning'
    else:
        return ''
