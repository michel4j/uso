import json

from django.utils.translation import gettext as _
from dynforms.fields import FieldType


class SampleTypes(FieldType):
    name = _("Sample Types")
    icon = "bi-paint-bucket"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"
    choices_type = 'checkbox'

    def is_multi_valued(self, subfield: str = None) -> bool:
        return True


class WasteTypes(FieldType):
    name = _("Waste Types")
    icon = "bi-paint-bucket"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"
    choices_type = 'checkbox'

    def is_multi_valued(self, subfield: str = None) -> bool:
        return True


class SampleHazards(FieldType):
    name = _("Hazards")
    icon = "bi-exclamation-triangle"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"
    choices_type = 'checkbox'

    def is_multi_valued(self, subfield: str = None) -> bool:
        return True

    def clean(self, value):
        return list(map(int, value))


class SafetyControls(FieldType):
    name = _("SafetyControls")
    icon = "bi-paint-bucket"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"
    choices_type = 'checkbox'

    def is_multi_valued(self, subfield: str = None) -> bool:
        return True


class Samples(FieldType):
    name = _("Sample List")
    icon = "bi-paint-bucket"
    options = ['required', 'multiple']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"
    required_subfields = ['sample', 'quantity']

    def is_multi_valued(self, subfield: str = None) -> bool:
        if subfield:
            return False
        return True

    @staticmethod
    def clean_sample(value):
        return int(value)


class SampleHazardReviews(FieldType):
    name = _("Hazard Reviews")
    icon = "bi-activity"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"
    choices_type = 'checkbox'

    def is_multi_valued(self, subfield: str = None) -> bool:
        if subfield:
            return False
        return True

    @staticmethod
    def clean_sample(value):
        return int(value)

    @staticmethod
    def clean_hazards(value):
        return json.loads(value) if isinstance(value, str) else value

    @staticmethod
    def clean_permissions(value):
        if isinstance(value, str):
            value = json.loads(value)
        return value

    @staticmethod
    def clean_keywords(value):
        if isinstance(value, str):
            return json.loads(value)
        if not isinstance(value, dict):
            return value
        return {}


class SampleEthicsReviews(FieldType):
    name = _("Ethics Reviews")
    icon = "bi-activity"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"

    def is_multi_valued(self, subfield: str = None) -> bool:
        if subfield:
            return False
        return True

    @staticmethod
    def tidy_value(values):
        if isinstance(values, list) and len(values):
            return values[0]

    def get_completeness(self, data):
        if not data:
            return 0.0
        valid = len([x.get('decision') for x in data if x.get('decision')])
        total = len(data)
        return 0.0 if total == 0 else float(valid) / total


def _get_value(val):
    """
    Extracts the value from the input, which can be a string or a list.
    :param val: The input value.
    :return: The cleaned value.
    """
    if isinstance(val, str):
        return val
    elif isinstance(val, list) and len(val):
        return val[0]
    return None


class Permissions(FieldType):
    name = _("Permissions")
    icon = "bi-key"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"

    def is_multi_valued(self, subfield: str = None) -> bool:
        return False


class EquipmentReviews(FieldType):
    name = _("Equipment Reviews")
    icon = "bi-activity"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"

    def is_multi_valued(self, subfield: str = None) -> bool:
        if subfield:
            return False
        return True
