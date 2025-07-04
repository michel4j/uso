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

    def is_multi_valued(self, subfield: str = None) -> bool:
        if subfield and subfield in ['techniques']:
            return True
        elif subfield:
            return False
        return True

    @staticmethod
    def clean_procedure(value):
        return value.strip()

    @staticmethod
    def clean_justification(value):
        return value.strip()

    @staticmethod
    def clean_techniques(value):
        if isinstance(value, list):
            return [to_int(val) for val in value]
        elif isinstance(value, str):
            return [to_int(value)]
        return [value]

    @staticmethod
    def clean_facility(value):
        if isinstance(value, list):
            return to_int(value[0])
        elif isinstance(value, str):
            return to_int(value)
        return value


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


class ReviewSummary(FieldType):
    name = _('Review Summary')
    icon = "bi-sliders"
    settings = ['label', 'options', ]
    options = ['nolabel', 'required']
    template_theme = "proposals/fields"
    required_subfields = ["review", "completed"]

    # def get_completeness(self, data):
    #     data = data if data else []
    #     return 0 if not data else len([_f for _f in [v.get('completed') for v in data] if _f]) / float(len(data))

    # def clean(self, value, multi=True, validate=False):
    #     value = super().clean(value, multi=multi, validate=validate)
    #
    #     if validate and not value.get('completed'):
    #         raise ValidationError("Review must be completed.")
    #     return value
