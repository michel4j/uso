

import functools
import operator
from collections import OrderedDict

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from dynforms.fields import FieldType


def to_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


class BeamlineReqs(FieldType):
    name = _("Beamline")
    icon = "bi-sliders"
    options = ['required', "repeat", "tags", "justification"]
    settings = ['label', 'options', ]
    template_theme = "proposals/fields"
    required_subfields = ['techniques', 'facility', 'procedure', 'justification']

    def coerce(self, val):
        if isinstance(val, dict):
            # clean strings
            for k in ['justification', 'procedure']:
                val[k] = val.get(k, '').strip()
        return val

    def clean(self, val, multi=True, validate=True):
        # prepare initial value dict
        if isinstance(val, dict):
            val = super().clean(val, multi=multi, validate=validate)

        # make sure values are clean in prepared list
        for req in val:
            techs = req.get('techniques', [])
            techs = techs if isinstance(techs, list) else [techs]
            tags = req.get('tags', [])
            tags = tags if isinstance(tags, list) else [tags]

            req['techniques'] = list(map(to_int, {_f for _f in techs if _f}))
            req['tags'] = list(map(to_int, {_f for _f in tags if _f}))
            req['facility'] = to_int(req.get('facility', None), "")
            req['shifts'] = to_int(req.get('shifts'), "")
            for k in ['justification', 'procedure']:
                req[k] = req.get(k, '').strip()

        # combine duplicate facilities
        groups = OrderedDict([(req.get('facility'), list()) for req in val])
        for req in val:
            groups[req.get('facility')].append(req)

        raw_requirements = []
        for key, group in list(groups.items()):
            new_req = {
                'facility': key,
            }
            for k in ['tags', 'techniques', 'procedure', 'justification', 'shifts']:
                new_req[k] = functools.reduce(operator.__add__, [_f for _f in [req[k] for req in group] if _f],
                                              type(group[0][k])())
            raw_requirements.append(new_req)

        # delete blank entries:
        requirements = [req for req in raw_requirements if any(req.values())]

        # validate reqs
        if validate:
            from beamlines import models
            invalid_fields = set()
            for req in requirements:
                invalid_fields |= {k for k, v in list(self.check_entry(req).items()) if not v}
                fac_id = req.get('facility')
                fac = None if not fac_id else models.Facility.objects.filter(pk=fac_id).first()
                if fac and not fac.flex_schedule and not req.get('shifts', 0):
                    raise ValidationError("'shifts' is required for the {} beamline".format(fac))
            if invalid_fields:
                raise ValidationError("must complete {} for all selected beamlines".format(', '.join(invalid_fields)))

        return requirements


class ReviewCycle(FieldType):
    name = _("Cycle")
    icon = "bi-sliders"
    options = ['required']
    settings = ['label', 'options', ]
    template_theme = "proposals/fields"


class Reviewers(FieldType):
    name = _("Reviewers")
    icon = "bi-person-vcard"
    options = ['required', 'hide', 'repeat']
    settings = ['label', 'options', ]
    template_theme = "proposals/fields"
    multi_valued = True

    def clean(self, val, multi=True, validate=False):
        if isinstance(val, dict):
            val = super().clean(val, multi=multi, validate=validate)
        return [] if not val else val


class ReviewSummary(FieldType):
    name = _('Review Summary')
    icon = "bi-sliders"
    settings = ['label', 'options', ]
    options = ['nolabel', 'required']
    template_theme = "proposals/fields"
    required_subfields = ["review", "completed"]
    multi_valued = True

    def get_completeness(self, data):
        data = data if data else []
        return 0 if not data else len([_f for _f in [v.get('completed') for v in data] if _f]) / float(len(data))

    def clean(self, val, multi=True, validate=False):
        if isinstance(val, dict):
            val = super().clean(val, multi=multi, validate=validate)

        val = val if val else []
        if validate:
            if not all([v.get('completed') for v in val]):
                raise ValidationError("All assigned reviews must be completed.")
        return val
