from django import template

register = template.Library()


@register.filter(name="has_perm")
def has_perm(user, arg):
    return user.has_any_perm(arg)


@register.filter(name="has_role")
def has_role(user, arg):
    return user.has_any_role(arg)


@register.filter(name='role_label')
def role_label(role):
    if ':' in role:
        role, realm = role.split(':')
    else:
        realm = ''
    role.replace('-', ' ').title()
    return ' '.join([role.replace('-', ' ').title(), realm.upper()]).strip()
