import copy
import itertools
import operator
import re
from functools import reduce

from django.conf import settings
from misc.blocktypes import BaseBlock, BLOCK_TYPES


USO_FACILITY_STAFF_ROLE = getattr(settings, "USO_FACILITY_STAFF_ROLE", "staff:+")
USO_FACILITY_ADMIN_ROLE = getattr(settings, "USO_FACILITY_ADMIN_ROLE", "admin:-")


class MyFacilities(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "beamlines/blocks/facilities.html"
    priority = 10

    def render(self, context):
        from . import models
        ctx = copy.copy(context)
        user = context['request'].user
        # generate filters for staff and admin roles
        staff_pattern = re.compile(re.sub(r'[+-]$', '(?P<acronym>.+)$', USO_FACILITY_STAFF_ROLE))
        admin_pattern = re.compile(re.sub(r'[+-]$', '(?P<acronym>.+)$', USO_FACILITY_ADMIN_ROLE))
        staff_acronyms = list(itertools.chain(*[
            staff_pattern.findall(role) for role in user.get_all_roles() if staff_pattern.match(role)
        ]))
        admin_acronyms = list(itertools.chain(*[
            admin_pattern.findall(role) for role in user.get_all_roles() if admin_pattern.match(role)
        ]))
        acronyms = staff_acronyms + admin_acronyms
        if acronyms:
            filters = reduce(operator.__or__, [
                models.Q(acronym__iexact=acronym) for acronym in staff_acronyms
            ], models.Q(pk__isnull=True))
        else:
            return None

        facilities = models.Facility.objects.filter(filters)
        if facilities.exists():
            ctx.update({
                "facilities": facilities,
            })
            return super().render(ctx)
