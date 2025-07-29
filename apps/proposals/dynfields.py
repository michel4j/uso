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
    required_subfields = ['techniques', 'facility', 'procedure']

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

    @staticmethod
    def clean_shifts(value):
        """
        Cleans the 'shifts' field to ensure it is an integer.
        """
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

    def is_multi_valued(self, subfield: str = None) -> bool:
        return not subfield

    @staticmethod
    def clean_completed(value):
        """
        Cleans the 'completed' field to ensure it is a boolean.
        """
        try:
            return int(value)
        except ValueError:
            raise ValidationError(_("The review must be 'completed."))

