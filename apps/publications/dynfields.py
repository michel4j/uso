from dynforms.fields import FieldType
from django.utils.translation import gettext as _


class SubjectArea(FieldType):
    name = _("Subject Area")
    icon = "bi-briefcase"
    options = ['required', 'hide', 'multiple', 'keywords']
    settings = ['label', 'options', ]
    template_theme = "publications/fields"

    def coerce(self, val):
        if isinstance(val.get('keywords'), list):
            val['keywords'] = "; ".join(val['keywords'])
            val['areas'] = [int(v) for v in val.get('areas', [])]
        return val


class ResearchArea(FieldType):
    name = _("Research Area")
    icon = "bi-briefcase"
    options = ['required', 'hide', 'inline']
    settings = ['label', 'options', ]
    template_theme = "publications/fields"

    def clean(self, val, multi=False, validate=True):
        if isinstance(val, list):
            return list(map(int, val))
        else:
            return []
