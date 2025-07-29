import json

from django.db.models import QuerySet
from django.forms.widgets import CheckboxSelectMultiple, HiddenInput


class HazardSelectMultiple(CheckboxSelectMultiple):
    pass


class HiddenListInput(HiddenInput):
    """
    A widget that renders a list of hidden inputs for each item in a list.
    """

    def format_value(self, value):
        if isinstance(value, list):
            return json.dumps(value)
        elif isinstance(value, QuerySet):
            return json.dumps(list(value.values_list('pk', flat=True)))
        elif isinstance(value, str):
            return value
        return "[]"

    def value_from_datadict(self, data, files, name):
        value = data.get(name, "[]")
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []