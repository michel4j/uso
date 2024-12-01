import uuid
from datetime import datetime, timedelta
from collections import OrderedDict



from dateutil import parser
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from dynforms.fields import FieldType
from dynforms.utils import Crypt


# Standard Fields
class StandardMixin(object):
    section = _("Standard")
    template_theme = "dynforms/fields"


class SingleLineText(FieldType, StandardMixin):
    name = _("Single Line")
    icon = "bi-input-cursor-text"
    options = ['hide', 'required', 'unique', 'repeat']
    units = ['chars', 'words']
    settings = ['label', 'width', 'options', 'minimum', 'maximum', 'units', 'default']

    def clean(self, val, multi=False, validate=True):
        val = super().clean(val, multi=multi, validate=validate)
        if isinstance(val, str):
            val = val.strip()
        return val


class ParagraphText(SingleLineText):
    name = _("Paragraph")
    icon = "bi-justify-left"
    options = ['hide', 'required', 'unique', 'repeat', 'counter']
    settings = ['label', 'size', 'options', 'minimum', 'maximum', 'units', 'default']


class RichText(ParagraphText):
    name = _("Rich Text")
    icon = "bi-text-indent-left"
    settings = ['label', 'size', 'options', 'minimum', 'maximum', 'units', 'default']


class MultipleChoice(FieldType, StandardMixin):
    name = _("Choices")
    icon = "bi-ui-radios"
    options = ['required', 'randomize', 'inline', 'hide', 'other']
    settings = ['label', 'options', 'choices']
    choices_type = 'radio'


class ScoreChoices(FieldType, StandardMixin):
    name = _("Score Choices")
    icon = "bi-ui-radios"
    options = ['required', 'inline', 'hide']
    settings = ['label', 'options', 'choices']
    choices_type = 'radio'

    def coerce(self, value):
        try:
            val = int(value)
        except (TypeError, ValueError):
            val = 0
        return val


class Number(SingleLineText):
    name = _("Number")
    icon = "bi-5-square"
    units = ['digits', 'value']
    settings = ['label', 'width', 'options', 'minimum', 'maximum', 'units', 'default']

    def coerce(self, value):
        try:
            val = int(value)
        except (TypeError, ValueError):
            val = 0
        return val


class CheckBoxes(FieldType, StandardMixin):
    name = _("Checkboxes")
    icon = "bi-check2-square"
    options = ['required', 'randomize', 'inline', 'hide', 'other']
    settings = ['label', 'options', 'choices']
    choices_type = 'checkbox'
    multi_valued = True


class DropDown(MultipleChoice):
    name = _("Dropdown")
    icon = "bi-chevron-down"
    options = ['required', 'randomize', 'inline', 'hide', 'multiple']
    settings = ['label', 'options', 'width', 'choices']


class NewSection(FieldType, StandardMixin):
    input_type = None
    name = _("Section")
    icon = "bi-dash-lg"
    options = ['hide', 'nolabel']
    settings = ['label', 'options']


# Fancy Fields
class FancyMixin(object):
    section = _("Fancy")
    template_theme = "dynforms/fields"


class FullName(FieldType, FancyMixin):
    name = _("Full Name")
    icon = "bi-person-vcard"
    options = ['required', 'hide', 'repeat']
    settings = ['label', 'options', ]
    required_subfields = ['first_name', 'last_name']


class Address(FullName):
    name = _("Address")
    icon = "bi-house"
    options = ['required', 'hide', 'department', 'labels']
    settings = ['label', 'options', ]
    required_subfields = ['street', 'city', 'region', 'country', 'code']

    def clean(self, val, multi=False, validate=True):
        val = super().clean(val, multi=multi, validate=validate)

        if validate:
            invalid_fields = set()
            if isinstance(val, list):
                for entry in val:
                    invalid_fields |= {k for k, v in list(self.check_entry(entry).items()) if not v}
            else:
                invalid_fields |= {k for k, v in list(self.check_entry(val).items()) if not v}

            if invalid_fields:
                raise ValidationError("Must complete {}".format(', '.join(invalid_fields)))
        return val


class MultiplePhoneNumber(FieldType, FancyMixin):
    name = _("Phone #s")
    icon = "bi-telephone"
    options = ['required', 'hide', 'repeat']
    settings = ['label', 'options', ]


class NameEmail(FullName):
    name = _("Name/Email")
    icon = "bi-person-vcard"
    options = ['required', 'hide', 'repeat']
    settings = ['label', 'options', ]
    required_subfields = ['first_name', 'last_name', 'email']

    def clean(self, val, multi=False, validate=True):
        val = super().clean(val, multi=multi, validate=validate)
        invalid_fields = set()
        if isinstance(val, list):
            entries = OrderedDict()
            for entry in val:
                key = "{}{}{}".format(
                    entry.get('first_name', '').strip(),
                    entry.get('last_name', '').strip(),
                    entry.get('email', '').strip()
                )
                entries[key.lower()] = entry
                invalid_fields |= {k for k, v in list(self.check_entry(entry).items()) if not v}
            val = list(entries.values())
        else:
            invalid_fields |= {k for k, v in list(self.check_entry(val).items()) if not v}

        if validate and invalid_fields:
            raise ValidationError("Must provide {} for all entries".format(', '.join(invalid_fields)))

        return val


class Equipment(FieldType, FancyMixin):
    name = _("Equipment")
    icon = "bi-plug"
    options = ['required', 'hide', 'repeat']
    settings = ['label', 'options']


class ContactInfo(FullName):
    name = _("Contact Info")
    icon = "bi-person-vcard"
    options = ['required', 'hide', 'repeat']
    settings = ['label', 'options', ]
    required_subfields = ['email', 'phone']


class NameAffiliation(FullName):
    name = _("Name/Affiliation")
    icon = "bi-person-vcard"
    options = ['required', 'hide', 'repeat']
    settings = ['label', 'options', ]
    required_subfields = ['first_name', 'last_name', 'affiliation']


class Email(FieldType, FancyMixin):
    name = _("Email")
    icon = "bi-envelope-at"
    options = ['required', 'unique', 'hide', 'repeat']
    units = ['chars']
    settings = ['label', 'width', 'options', 'minimum', 'maximum', 'units', 'default']


class Date(FieldType, FancyMixin):
    name = _("Date")
    icon = "bi-calendar-date"
    options = ['required', 'unique', 'hide', 'multiple']
    settings = ['label', 'options']


class DatePreference(FieldType, FancyMixin):
    name = _("Date Preferences")
    icon = "bi-calendar-heart"
    options = ['required', 'unique', 'hide', 'multiple']
    settings = ['label', 'options']


class Time(FieldType, FancyMixin):
    name = _("Time")
    icon = "bi-clock"
    settings = ['label']


class WebsiteURL(FieldType, FancyMixin):
    name = _("Website URL")
    icon = "bi-link"
    options = ['required', 'unique', 'hide', 'repeat']
    units = ['chars', 'words']
    settings = ['label', 'width', 'options', 'minimum', 'maximum', 'units', 'default']


# class GridField(FieldType, FancyMixin):
#     name = _("Grid")
#     icon = "bi-table"
#     settings = ['label', 'options',]
#  
# class LikertField(FieldType, FancyMixin):
#     name = _("Likert")
#     icon = "bi-ui-radios-grid"
#     settings = ['label', 'options',]

class File(FieldType, FancyMixin):
    name = _("File")
    icon = "bi-file"
    options = ['required', 'hide', 'repeat']
    settings = ['label', 'options', ]


class PhoneNumber(FieldType, FancyMixin):
    name = _("Phone #")
    icon = "bi-telephone"
    options = ['required', 'hide', 'repeat']
    settings = ['label', 'width', 'options', ]


class Throttle(FieldType, FancyMixin):
    name = _("Throttle")
    icon = "bi-stoplights"
    options = ['hide']
    settings = ['label', 'options']

    def clean(self, value, validate=True, multi=False):
        if isinstance(value, list):
            value = value[0]

        start = datetime.now() - timedelta(seconds=20)
        try:
            message = Crypt.decrypt(value)
            print("MESSAGE", message)
        except ValueError:
            if validate:
                raise ValidationError('Something funny happened with the form. Reload the page and start again.')
        else:
            start = parser.parse(message)
        now = datetime.now()
        if (now - start).total_seconds() < 10:
            raise ValidationError('Did you take the time to read the questions?')

        return value
