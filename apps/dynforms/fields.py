
from collections import OrderedDict

from django.forms import ValidationError
from django.utils.text import slugify
from django.utils.translation import gettext as _
from model_utils import Choices

DEFAULT_SETTINGS = {
    "label": "%s %s",
    "instructions": "",
    "size": "medium",
    "width": "full",
    "options": [],
    "choices": ["First Choice"],
    "default_choices": [],
}


class FieldTypeMeta(type):
    def __init__(cls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cls.key = slugify(cls.__name__)
        if hasattr(cls, 'template_theme'):
            cls.templates = ["%s/%s.html" % (cls.template_theme, cls.key), "dynforms/fields/nofield.html"]
        else:
            cls.templates = ["dynforms/fields/%s.html" % cls.key, "dynforms/fields/nofield.html"]

        if not hasattr(cls, 'plugins'):
            cls.plugins = {}
        else:
            cls.plugins[cls.key] = cls

    def get_all(self, *args, **kwargs):
        info = {}
        for p in list(self.plugins.values()):
            section = getattr(p, 'section', _("Application"))
            if section not in info:
                info[section] = []
            info[section].append(p(*args, **kwargs))
        return info

    def get_type(self, key):
        ft = self.plugins.get(key, None)
        if ft is not None:
            return ft()


CHOICE_INFO = {
    'medium': _('Medium'),
    'small': _('Small'),
    'large': _('Large'),
    'full': _('Full'),
    'half': _('Half'),
    'third': _('Third'),
    'chars': _('Characters'),
    'words': _('Words'),
    'value': _('Value'),
    'digits': _('Digits'),
    'required': _('Required'),
    'unique': _('Unique'),
    'randomize': _('Randomize'),
    'hide': _('Hide'),
    'inline': _('Inline'),
    'other': _('Add Other'),
    'repeat': _('Repeatable'),
    'nolabel': _('No Label'),
}


def _build_choices(pars):
    opts = []
    for k in pars:
        if isinstance(k, str):
            v = CHOICE_INFO.get(k, k.capitalize())
            opts.append((k, v))
        elif isinstance(k, tuple):
            opts.append(k)
    return Choices(*opts)


def _val_to_list(value):
    if isinstance(value, dict):
        try:
            new_value = {
                int(k): v
                for k, v in list(value.items())
            }
        except ValueError:
            out_value = [x[1] for x in sorted(value.items())]
        else:
            out_value = [x[1] for x in sorted(new_value.items())]
        return out_value
    elif hasattr(value, '__getitem__') and not isinstance(value, str):
        return value
    else:
        return []


class FieldType(object, metaclass=FieldTypeMeta):
    name = _("Noname Field")
    icon = "bi-input-cursor"
    multi_valued = False
    sizes = ["medium", "small", "large"]
    widths = ["full", "half", "third"]
    units = ["chars", "words", "values", "digits"]
    options = ["required", "unique", "randomize", "hide", "inline", "other", "repeat"]
    choices_type = 'checkbox'  # 'radio'
    settings = ["label", "name", "instructions"]
    required_subfields = []

    def check_entry(self, row):
        if not isinstance(row, dict):
            return {}
        validity = {
            key: bool(row.get(key, '')) for key in self.required_subfields
        }
        return validity

    def get_completeness(self, data):
        if not data:
            return 0.0
        elif len(self.required_subfields) == 0:
            return 1.0
        else:
            invalid_fields = []
            if isinstance(data, list):
                for entry in data:
                    invalid_fields += [k for k, v in list(self.check_entry(entry).items()) if not v]
                total = len(data) * len(self.required_subfields)
            else:
                invalid_fields += [k for k, v in list(self.check_entry(data).items()) if not v]
                total = len(self.required_subfields)
            return 1.0 if total == 0 else (1.0 - len(invalid_fields) / float(total))

    def coerce(self, val):
        if isinstance(val, dict):
            clean_val = {k: v[0] for k, v in list(val.items()) if isinstance(v, list)}
            val.update(clean_val)
            val = {k: v for k, v in list(val.items()) if v}
        return val

    def clean(self, val, multi=False, validate=False):
        """Parse and Validate field and return clean value"""
        try:
            if isinstance(val, dict) and (multi or self.multi_valued):
                val = list(map(dict, zip(*[[(k, v) for v in value] for k, value in val.items()])))
            elif not isinstance(val, list):
                val = [val]
            val = list(map(self.coerce, val))
        except ValueError:
            if validate:
                raise ValidationError(_('Invalid value: %(value)s'), code='invalid', params={'value': val}, )
        else:
            if not (multi or self.multi_valued) and val:
                return val[0]
            else:
                return [v for v in val if v]

    def get_default(self, page=None, pos=None):
        if pos is None: pos = 0
        if page is None: page = 0
        tag = "%03d" % (100 * page + pos)
        field = {'field_type': self.key}
        for k in self.settings:
            if k in DEFAULT_SETTINGS:
                if k == 'label':
                    field[k] = DEFAULT_SETTINGS[k] % (self.name, tag)
                    field['name'] = slugify(str(field[k]))
                elif k == "choices":
                    field[k] = DEFAULT_SETTINGS[k]
                    field['default_choices'] = DEFAULT_SETTINGS["default_choices"]
                else:
                    field[k] = DEFAULT_SETTINGS[k]
        return field

    def option_choices(self):
        return _build_choices(self.options)

    def size_choices(self):
        return _build_choices(self.sizes)

    def width_choices(self):
        return _build_choices(self.widths)

    def units_choices(self):
        return _build_choices(self.units)

    def get_choices(self, field_name):
        return {
            'options': _build_choices(self.options),
            'size': _build_choices(self.sizes),
            'width': _build_choices(self.widths),
            'units': _build_choices(self.units)

        }.get(field_name, [])
