
import random

from django import template
from django.utils.safestring import mark_safe

from dynforms.fields import FieldType

register = template.Library()


def _get_field_value(context, field):
    field_name = field['name']
    default = field.get('defaults', '')
    form = context.get('form')

    if not form:
        return default

    if form.is_bound:
        data = form.cleaned_data.get('details', {})
        value = data.get(field_name)
        if value is not None:
            return value

    if getattr(form, 'instance', None) and hasattr(form.instance, 'get_field_value') and form.instance.pk:
        value = form.instance.get_field_value(field_name)
        if value is not None:
            return value

    value = form.initial.get(field_name, default)
    return '' if value is None else value


@register.simple_tag(takes_context=True)
def show_field(context, field, repeatable=False):
    field_type = FieldType.get_type(field['field_type'])
    all_data = _get_field_value(context, field)

    t = template.loader.get_template(field_type.templates[0])
    if field_type.multi_valued:
        all_data = [] if all_data == '' else all_data

    if not repeatable or not isinstance(all_data, list):
        all_data = [all_data]

    if repeatable and all_data == []:
        all_data = ['']

    ctx = {} if not repeatable else {'repeatable': f"{field['name']}-repeatable"}
    ctx.update(context.flatten())

    rendered = ""
    for i, data in enumerate(all_data):
        if "choices" in field and "other" in field['options'] and isinstance(data, list):
            oc_set = set(data) - set(field['choices'])
            if oc_set:
                field['other_choice'] = next(iter(oc_set))
        repeat_index = i if repeatable else ""

        ctx.update({'field': field, 'data': data, 'repeat_index': repeat_index})
        rendered += t.render(ctx)

    return mark_safe(rendered)


@register.simple_tag(takes_context=True)
def show_builder_field(context, field, repeatable=False):
    all_data = field.get_data(context)

    t = template.loader.get_template(field.type.templates[0])
    if field.type.multi_valued:
        all_data = [] if all_data == '' else all_data

    if not (repeatable and isinstance(all_data, list)):
        all_data = [all_data]

    if repeatable and all_data == []:
        all_data = ['']

    ctx = {} if not repeatable else {'repeatable': f"{field.name}-repeatable"}
    ctx.update(context.flatten())

    rendered = ""
    choices = field.get_choices()
    options = field.get_options()
    for i, data in enumerate(all_data):
        if choices and "other" in options and isinstance(data, list):
            oc_set = set(data) - set(choices)
            if oc_set:
                field.set_attr('other_choice', next(iter(oc_set)))
        repeat_index = i if repeatable else ""

        ctx.update({'field': field.specs(), 'data': data, 'repeat_index': repeat_index})
        rendered += t.render(ctx)

    return mark_safe(rendered)


@register.filter
def group_choices(field, defaults):
    if not defaults:
        defaults = field.get('default', [])
    if 'values' in field:
        choices = list(zip(field['choices'], field['values']))
    else:
        choices = list(zip(field['choices'], field['choices']))
    ch = [{
        'label': l,
        'value': l if v is None else v,
        'selected': v in defaults or v == defaults
    } for l, v in choices]
    return ch


@register.filter
def group_scores(field, default):
    choices = [
        {
            'score': i + 1,
            'label': l,
            'value': '' if 'values' not in field else field['values'][i],
            'checked': default in [(i + 1), str(i + 1)],
        } for i, l in enumerate(field['choices'])
    ]

    return choices


@register.filter
def required(field):
    if 'required' in field.get('options', []):
        return 'required'
    else:
        return ''


@register.filter
def randomize_choices(choices, field):
    tmp = choices[:]
    if 'randomize' in field.get('options', []):
        random.shuffle(tmp)
    return tmp


@register.filter
def page_errors(validation, page):
    return {} if not isinstance(validation, dict) else validation.get('pages', {}).get(page, {})


@register.filter
def readable(value):
    return value.replace('_', ' ').capitalize()


@register.inclusion_tag('dynforms/form-tabs.html', takes_context=True)
def render_form_tabs(context):
    return context


@register.simple_tag(takes_context=True)
def define(context, **kwargs):
    for k, v in list(kwargs.items()):
        context[k] = v


@register.simple_tag(takes_context=True)
def check_error(context, field_name, errors, label='error'):
    if field_name in errors:
        return label
    return ""


@register.simple_tag(takes_context=True)
def field_label(context, field_name):
    names = {f['name']: f['label'] for f in context['page']['fields']}
    return names.get(field_name, '')
