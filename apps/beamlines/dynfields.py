from django.utils.translation import gettext as _

from dynforms.fields import FieldType


class Ancillary(FieldType):
    name = _("Ancillaries")
    icon = "bi-paint-bucket"
    template_theme = "beamlines/fields"
    options = ['required', 'hide', 'multiple']
    settings = ['label', 'options', 'width']
    multi_valued = True

    def coerce(self, val):
        return val

    def clean(self, val, multi=True, validate=False):
        return val


class TechnicalTags(FieldType):
    name = _("Technical Tags")
    icon = "bi-paint-bucket"
    template_theme = "beamlines/fields"
    options = ['required', 'hide', 'nolabel']
    settings = ['label', 'options']

    def clean(self, val, multi=False, validate=True):
        val = super().clean(val, multi=multi, validate=validate)
        if isinstance(val, str):
            val = int(val.strip())
        return val
