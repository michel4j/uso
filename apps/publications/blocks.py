from misc.blocktypes import BaseBlock, BLOCK_TYPES
import copy
from . import stats
import math
from . import views


class PublicationsBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "publications/blocks/publications.html"
    priority = 4

    def check_allowed(self, request):
        return request.user.is_authenticated

    def render(self, context):
        ctx = copy.copy(context)
        user = context['request'].user

        publications = user.publications.all()
        matches = views.get_author_matches(user)

        ctx.update({
            "words": stats.get_keywords(publications, transform=math.sqrt),
            "matches": matches
        })
        if not publications and not matches:
            return ""

        return super().render(ctx)
