from dynforms.fields import FieldType
from django.utils.translation import gettext as _


class ResearchArea(FieldType):
    name = _("Research Area")
    options = ['required', 'hide', 'inline']
    template_name = "publications/fields/researcharea.html"


class SubjectArea(FieldType):
    name = _("Subject Area")
    options = ['required', 'hide', 'multiple']
    template_name = "publications/fields/subjectarea.html"
    required_subfields = ['areas', 'keywords']

    def is_multi_valued(self, subfield: str = None) -> bool:
        if subfield in ['areas']:
            return True
        return False

    @staticmethod
    def clean_areas(value):
        return [int(val) for val in value]
