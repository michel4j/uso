from django import template

register = template.Library()


@register.simple_tag()
def folio_status(state, draft='X0', warn='X1', info='X2', success='X3', danger='X4', default='bg-darken'):
    if state == warn:
        return 'bg-warning'
    elif state == draft:
        return 'bg-darken'
    elif state == info:
        return 'bg-info'
    elif state == success:
        return 'bg-success'
    elif state == danger:
        return 'bg-danger'
    else:
        return default
