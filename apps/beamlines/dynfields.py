from django.utils.translation import gettext as _

from dynforms.fields import FieldType


class Ancillary(FieldType):
    name = _("Ancillaries")
    icon = "bi-paint-bucket"
    template_theme = "beamlines/fields"
    options = ['required', 'hide', 'multiple']
    settings = ['label', 'options', 'width']

    def is_multi_valued(self, subfield: str = None) -> bool:
        if subfield in ['labs', 'equipment']:
            return True
        return False

