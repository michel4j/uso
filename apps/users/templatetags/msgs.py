import re

from django import template
from django.contrib import messages
from django.template.defaultfilters import stringfilter
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="msg_icon", needs_autoescape=True)
def msg_icon(tag, autoescape=None):
    ICONS = {
        'debug': '<i class="bi-bug text-primary"></i>',
        'info': '<i class="bi-info-circle text-info"></i>',
        'success': '<i class="bi-check2-circle  text-success"></i>',
        'warning': '<i class="bi-exclamation-circle text-warning"></i>',
        'error': '<i class="bi-exclamation-circle text-danger"></i>',
    }
    icon = ''
    if autoescape:
        tag = conditional_escape(tag)
    if tag:
        tag = tag.split()[0]
        icon = ICONS.get(tag, '')
    return mark_safe(icon)


@register.filter(name="msg_type", needs_autoescape=True)
def msg_type(level, autoescape=None):
    code = {
        messages.INFO: 'info',
        messages.SUCCESS: 'success',
        messages.WARNING: 'warning',
        messages.ERROR: 'error',
        messages.DEBUG: 'info'
    }
    return code.get(level, 'info')


@register.filter(name="msg_compose", needs_autoescape=True)
def msg_compose(msg, autoescape=None):
    text = '<div class="activity-item">{0}<div class="activity">{1}</div></div>'.format(msg_icon(msg.tags), msg)
    return mark_safe(text)


CONSONANT_SOUND = re.compile(r'''
one(![ir])
''', re.IGNORECASE | re.VERBOSE)
VOWEL_SOUND = re.compile(r'''
[aeio]|
u([aeiou]|[^n][^aeiou]|ni[^dmnl]|nil[^l])|
h(ier|onest|onou?r|ors\b|our(!i))|
[fhlmnrsx]\b
''', re.IGNORECASE | re.VERBOSE)


@register.filter
@stringfilter
def an(text):
    """
    Guess "a" vs "an" based on the phonetic value of the text.

    "An" is used for the following words / derivatives with an unsounded "h":
    heir, honest, hono[u]r, hors (d'oeuvre), hour

    "An" is used for single consonant letters which start with a vowel sound.

    "A" is used for appropriate words starting with "one".

    An attempt is made to guess whether "u" makes the same sound as "y" in
    "you".
    """

    if not CONSONANT_SOUND.match(text) and VOWEL_SOUND.match(text):
        return 'an {0}'.format(text)
    return 'a {0}'.format(text)
