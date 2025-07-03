from dynforms.fields import FieldType
from django.utils.translation import gettext as _


class SubjectArea(FieldType):
    name = _("Subject Area")
    options = ['required', 'hide', 'multiple', 'keywords']
    template_name = "publications/fields/subjectarea.html"
    multi_valued = True

    def clean(self, value, multi=False, validate=True):

        if 'keywords' in value and isinstance(value['keywords'], list):
            value['keywords'] = '; '.join(value['keywords']).strip()

        return {
            'keywords': value.get('keywords', '').strip(),
            'areas': [int(v) for v in value.get('areas', [])]
        }


class ResearchArea(FieldType):
    name = _("Research Area")
    options = ['required', 'hide', 'inline']
    template_name = "publications/fields/researcharea.html"

    def clean(self, val, multi=False, validate=True):
        if isinstance(val, list):
            return list(map(int, val))
        else:
            return []
