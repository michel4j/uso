from django import template

register = template.Library()


@register.simple_tag()
def folio_status(state, draft='X0', warn='X1', info='X2', success='X3', danger='X4', default=''):
    if state == warn:
        return 'callout-warning'
    elif state == draft:
        return 'callout-secondary'
    elif state == info:
        return 'callout-info'
    elif state == success:
        return 'callout-success'
    elif state == danger:
        return 'callout-danger'
    else:
        return default
