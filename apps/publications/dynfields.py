from dynforms.fields import FieldType
from django.utils.translation import gettext as _


class ResearchArea(FieldType):
    name = _("Research Area")
    options = ['required', 'hide', 'inline']
    template_name = "publications/fields/researcharea.html"
    multi_valued = True

    def clean(self, value):
        print(value)
        return value


class SubjectArea(FieldType):
    name = _("Subject Area")
    options = ['required', 'hide', 'multiple', 'keywords']
    template_name = "publications/fields/subjectarea.html"
    multi_valued = False
    subfields = {
        'areas': ResearchArea
    }