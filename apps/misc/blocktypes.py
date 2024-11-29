from collections import defaultdict

from django.utils.text import slugify
from django.utils.translation import gettext as _
from model_utils import Choices

from misc.utils import load

BLOCK_TYPES = Choices(
    ('dashboard', _('Dashboard Widgets')),
)


def autodiscover():
    load('blocks')


class BlockMeta(type):
    def __init__(cls, *args, **kwargs):
        cls.key = slugify(str(cls.__name__))
        cls.code = "_".join([cls.__module__.split('.')[0], cls.__name__])
        if not hasattr(cls, 'plugins'):
            cls.plugins = defaultdict(list)
        priority = getattr(cls, "priority", len(cls.plugins[cls.block_type]))
        cls.plugins[cls.block_type].insert(priority, cls)

    def get_plugins(self, block_type=BLOCK_TYPES.dashboard):
        return [p() for p in self.plugins[block_type] if p != BaseBlock]


class BaseBlock(object, metaclass=BlockMeta):
    title = 'Block Title'
    block_type = BLOCK_TYPES.dashboard
    style_classes = ""
    template_name = ''
    src_url = ''
    reload_freq = 0

    def check_allowed(self, request):
        return True

    def get_template_name(self):
        return self.template_name

    def render(self, context):
        context['block_object'] = self
        t = context.template.engine.get_template(self.get_template_name())
        return t.render(context)
