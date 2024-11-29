from django import template
from django.utils.safestring import mark_safe

from misc import navigation

register = template.Library()


@register.simple_tag(takes_context=True)
def show_menu(context):
    request = context['request']
    items = navigation.BaseNav.get_menus()
    nav_items = sorted([m for m in items if m.allowed(request)], key=lambda x: x.weight)
    nav_template = template.loader.get_template("misc/nav.html")
    rendered = '<ul class="menu">'
    for nav in nav_items:
        rendered += nav_template.render({
            'nav': nav,
            'active': nav.active(request),
            'submenu': nav.sub_menu(request),
        })
    rendered += '</ul>'
    return mark_safe(rendered)
