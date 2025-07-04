import json

from django.utils.translation import gettext as _

from dynforms.fields import FieldType


class SampleTypes(FieldType):
    name = _("Sample Types")
    icon = "bi-paint-bucket"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"
    choices_type = 'checkbox'

    def is_multi_valued(self, subfield: str = None) -> bool:
        return True


class WasteTypes(FieldType):
    name = _("Waste Types")
    icon = "bi-paint-bucket"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"
    choices_type = 'checkbox'

    def is_multi_valued(self, subfield: str = None) -> bool:
        return True


class SampleHazards(FieldType):
    name = _("Hazards")
    icon = "bi-exclamation-triangle"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"
    choices_type = 'checkbox'

    def is_multi_valued(self, subfield: str = None) -> bool:
        return True


class SafetyControls(FieldType):
    name = _("SafetyControls")
    icon = "bi-paint-bucket"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"
    choices_type = 'checkbox'

    def is_multi_valued(self, subfield: str = None) -> bool:
        return True


class Samples(FieldType):
    name = _("Sample List")
    icon = "bi-paint-bucket"
    options = ['required', 'multiple']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"
    required_subfields = ['sample', 'quantity']

    def is_multi_valued(self, subfield: str = None) -> bool:
        if subfield:
            return False
        return True

    @staticmethod
    def clean_sample(value):
        return int(value)


class SampleHazardReviews(FieldType):
    name = _("Hazard Reviews")
    icon = "bi-activity"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"
    choices_type = 'checkbox'

    def is_multi_valued(self, subfield: str = None) -> bool:
        if subfield:
            return False
        return True

    @staticmethod
    def clean_sample(value):
        return int(value)

    @staticmethod
    def clean_hazards(value):
        return json.loads(value) if isinstance(value, str) else value

    @staticmethod
    def clean_permissions(value):
        if isinstance(value, str):
            value = json.loads(value)
        return value

    @staticmethod
    def _keywords(value):

        return {
            k: v[0].strip() if isinstance(v, list) else v.strip()
            for k, v in list(value.items()) if k and v
        }

    # def clean(self, val, multi=True, validate=True):
    #     from . import models
    #
    #     # prepare initial value dict
    #     if isinstance(val, dict):
    #         val = super().clean(val, multi=multi, validate=validate)
    #
    #     if not isinstance(val, list):
    #         return []
    #
    #     for sample in val:
    #         sample['sample'] = int(sample['sample'])
    #         sample['rejected'] = bool(sample.get('rejected'))
    #
    #         # Hazards
    #         hazards = sample.pop('hazards', [])
    #         if isinstance(hazards, str):
    #             hazards = json.loads(hazards)
    #
    #         if isinstance(hazards, list):
    #             sample['hazards'] = hazards
    #
    #         # Permissions
    #         perms = sample.pop('permissions', None)
    #         if isinstance(perms, str):
    #             perms = json.loads(perms)
    #
    #         if isinstance(perms, dict):
    #             perms.update({
    #                 p: 'all'
    #                 for p in
    #                 models.Hazard.objects.filter(pk__in=sample['hazards'], permissions__isnull=False).values_list(
    #                     'permissions__code', flat=True
    #                 )
    #             })
    #             sample['permissions'] = {
    #                 k: v for k, v in list(perms.items()) if v != 'none'
    #             }
    #
    #         # keywords
    #         keywords = sample.pop('keywords', {})
    #         if isinstance(keywords, dict):
    #             sample['keywords'] = {
    #                 k: v[0].strip() if isinstance(v, list) else v.strip()
    #                 for k, v in list(keywords.items()) if k and v
    #             }
    #
    #     return val


class SampleEthicsReviews(FieldType):
    name = _("Ethics Reviews")
    icon = "bi-activity"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"

    def is_multi_valued(self, subfield: str = None) -> bool:
        if subfield:
            return False
        return True

    @staticmethod
    def tidy_value(values):
        if isinstance(values, list) and len(values):
            return values[0]

    def get_completeness(self, data):
        if not data:
            return 0.0
        valid = len([x.get('decision') for x in data if x.get('decision')])
        total = len(data)
        return 0.0 if total == 0 else float(valid) / total

    # def clean(self, val, multi=False, validate=True):
    #     # prepare initial value dict
    #     if isinstance(val, dict):
    #         val = super().clean(val, multi=multi, validate=validate)
    #
    #     if not isinstance(val, list):
    #         return []
    #
    #     for sample in val:
    #         sample['sample'] = int(sample['sample'])
    #
    #     if validate:
    #         _invalid = []
    #         if not all([x.get('decision') for x in val]):
    #             _invalid.append(_('All samples need a decision.'))
    #         if not all([x.get('expiry') for x in val if x.get('decision') == 'ethics']):
    #             _invalid.append(_('Valid Certificate needs expiry date.'))
    #         if _invalid:
    #             raise ValidationError(" ".join(_invalid), code='required')
    #     return val


def _get_value(val):
    """
    Extracts the value from the input, which can be a string or a list.
    :param val: The input value.
    :return: The cleaned value.
    """
    if isinstance(val, str):
        return val
    elif isinstance(val, list) and len(val):
        return val[0]
    return None


class Permissions(FieldType):
    name = _("Permissions")
    icon = "bi-key"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"

    def is_multi_valued(self, subfield: str = None) -> bool:
        return not subfield

    # def clean(self, val, multi=False, validate=True):
    #     values = {
    #         key: _get_value(value) for key, value in val.items()
    #     }
    #     return {
    #         k: v for k, v in values.items() if v is not None
    #     }


class EquipmentReviews(FieldType):
    name = _("Equipment Reviews")
    icon = "bi-activity"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "samples/fields"

    def is_multi_valued(self, subfield: str = None) -> bool:
        if subfield:
            return False
        return True

    # @staticmethod
    # def tidy_value(values):
    #     if isinstance(values, list) and len(values):
    #         return values[0]
    #     else:
    #         return values
    #
    # def get_completeness(self, data):
    #     if not data:
    #         return 0.0
    #     valid = len([x.get('decision') for x in data if x.get('decision')])
    #     total = len(data)
    #     return 0.0 if total == 0 else float(valid) / total
    #
    # def clean(self, val, multi=False, validate=True):
    #     # prepare initial value dict
    #
    #     if isinstance(val, dict):
    #         val = super().clean(val, multi=multi, validate=validate)
    #
    #     for eq in val:
    #         eq['name'] = self.tidy_value(eq['name'])
    #
    #     if not isinstance(val, list):
    #         return []
    #
    #     return val
