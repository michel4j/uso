from django import template

register = template.Library()


@register.filter(name="has_perm")
def has_perm(user, args):
    return user.has_perms([args])


@register.filter(name="has_role")
def has_role(user, args):
    return user.has_role(args)


@register.filter(name='role_label')
def role_label(role):
    if ':' in role:
        role, realm = role.split(':')
    else:
        realm = ''
    role.replace('-', ' ').title()
    return ' '.join([role.replace('-', ' ').title(), realm.upper()]).strip()
