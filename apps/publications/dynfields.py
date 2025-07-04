from dynforms.fields import FieldType
from django.utils.translation import gettext as _


class ResearchArea(FieldType):
    name = _("Research Area")
    options = ['required', 'hide', 'inline']
    template_name = "publications/fields/researcharea.html"


class SubjectArea(FieldType):
    name = _("Subject Area")
    options = ['required', 'hide']
    template_name = "publications/fields/subjectarea.html"

    def is_multi_valued(self, subfield: str = None) -> bool:
        if subfield in ['areas']:
            return True
        return False

    def clean_areas(self, value):
        return [int(val) for val in value]
