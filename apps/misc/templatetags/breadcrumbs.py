from django import template
from django.urls import reverse, resolve, NoReverseMatch

register = template.Library()


@register.inclusion_tag('misc/breadcrumb.html', takes_context=True)
def breadcrumb(context, label, *args, **kwargs):
    """If args is are provided, the first entry should be the url """

    crumb_name = label
    request = context['request']
    current = resolve(request.path)

    if args:
        url = args[0]
        crumb_active = current.url_name == url
        args = args[1:]
        try:
            crumb_url = reverse(url, args=args, kwargs=kwargs)
        except NoReverseMatch:
            crumb_url = ""
    else:
        crumb_url = ""
        crumb_active = True

    return {
        'crumbs': [{
            'url': crumb_url,
            'name': crumb_name,
            'active': crumb_active
        }]
    }


@register.inclusion_tag('misc/breadcrumb.html', takes_context=True)
def view_breadcrumbs(context):
    """If args is are provided, the first entry should be the url """

    view = context['view']
    request = context['request']

    if hasattr(view, 'get_breadcrumbs'):
        crumbs = view.get_breadcrumbs()
    else:
        crumbs = []
    for crumb in crumbs:
        crumb['active'] = request.path == crumb['url']

    return {
        'crumbs': crumbs
    }
