

import functools
import operator
from collections import OrderedDict
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from dynforms.fields import FieldType


def to_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


class BeamlineReqs(FieldType):
    name = _("Beamline")
    icon = "bi-sliders"
    options = ['required', "repeat", "justification"]
    settings = ['label', 'options', ]
    template_theme = "proposals/fields"
    required_subfields = ['techniques', 'facility', 'procedure', 'justification']

    def coerce(self, value: Any, *flags):
        if 'facility' in flags and isinstance(value, list):
            return [to_int(val) for val in value]
        elif 'shifts' in flags and isinstance(value, str):
            return to_int(value)
        elif 'tags' in flags and isinstance(value, list):
            return value
        elif isinstance(value, list):
            return value[0].srip()
        return value[0]


class ReviewCycle(FieldType):
    name = _("Cycle")
    icon = "bi-sliders"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "proposals/fields"


class Reviewers(FieldType):
    name = _("Reviewers")
    icon = "bi-person-vcard"
    options = ['required', 'hide', 'repeat']
    settings = ['label', 'options', ]
    template_theme = "proposals/fields"
    multi_valued = True

    def coerce(self, value: Any, *flags):
        return value


class ReviewSummary(FieldType):
    name = _('Review Summary')
    icon = "bi-sliders"
    settings = ['label', 'options', ]
    options = ['nolabel', 'required']
    template_theme = "proposals/fields"
    required_subfields = ["review", "completed"]
    multi_valued = True

    def get_completeness(self, data):
        data = data if data else []
        return 0 if not data else len([_f for _f in [v.get('completed') for v in data] if _f]) / float(len(data))

    def clean(self, value, multi=True, validate=False):
        value = super().clean(value, multi=multi, validate=validate)

        if validate and not value.get('completed'):
            raise ValidationError("Review must be completed.")
        return value
