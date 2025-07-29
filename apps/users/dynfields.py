from django.utils.translation import gettext as _

from dynforms.fields import FieldType


class Sector(FieldType):
    name = _("Sector")
    icon = "bi-box"
    options = ['required', 'hide', 'inline']
    settings = ['label', 'options', ]
    template_name = "users/fields/sector.html"


class Staff(Sector):
    name = _("Staff Classes")
    template_name = "users/fields/staff.html"


class Students(Sector):
    name = _("Student Classes")
    template_name = "users/fields/students.html"
