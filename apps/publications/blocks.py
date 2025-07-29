from misc.blocktypes import BaseBlock, BLOCK_TYPES
import copy
from django.db.models import Count
import math
from . import stats
from . import views


def title_case(text: str ) -> str:
    """
    Convert a string to title-case but preserve existing uppercase.
    For example, "this is a TEST" becomes "This Is A TEST",
    :param text: The input string to convert.
    :return: The title-cased string.
    """
    return ' '.join([w.title() if w.islower() else w for w in text.split()])


class PublicationsBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "publications/blocks/publications.html"
    priority = 4

    def get_context_data(self):
        ctx = super().get_context_data()
        user = self.request.user

        publications = user.publications
        if not publications.exists():
            self.visible = False
        else:
            stats_data = user.publications.values('kind').annotate(count=Count('pk'))
            matches = views.get_author_matches(user)
            stats_info = {entry['kind'].title(): entry['count'] for entry in stats_data}
            stats_info['New Matches'] = matches

            ctx.update({
                "words": stats.get_keywords(publications, transform=math.sqrt),
                "matches": matches,
                "stats": stats_info,
            })

        return ctx
