from django.utils.translation import gettext as _

from dynforms.fields import FieldType


class Sector(FieldType):
    name = _("Sector")
    icon = "bi-box"
    options = ['required', 'hide', 'inline']
    settings = ['label', 'options', ]
    template_theme = "users/fields"


class Staff(Sector):
    name = _("Staff Classes")


class Students(Sector):
    name = _("Student Classes")
