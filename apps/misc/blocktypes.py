from collections import defaultdict

from django.template import RequestContext
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
        super().__init__(*args, **kwargs)

    def get_plugins(self, block_type=BLOCK_TYPES.dashboard):
        return [p for p in self.plugins[block_type] if p != BaseBlock]


class BaseBlock(object, metaclass=BlockMeta):
    title = 'Block Title'
    block_type = BLOCK_TYPES.dashboard
    style_classes = "bg-body-tertiary"
    width_classes = "col-sm-12 col-md-6 col-lg-4"
    template_name = ''
    src_url = ''
    reload_freq = 0
    visible = True

    def __init__(self, context: RequestContext):
        self.request = context.request
        self.context = context

    def check_allowed(self) -> bool:
        """
        Checks if the block is allowed to be displayed based on the request.
        Override this method in subclasses to implement custom logic.
        """
        return self.request.user.is_authenticated

    def get_style_classes(self):
        """
        Returns the CSS classes for the style of the block.
        """
        return self.style_classes

    def get_width_classes(self) -> str:
        """
        Returns the CSS classes for the width of the block.
        """
        return self.width_classes

    def get_template_name(self) -> str:
        """
        Returns the template name for the block.
        Override this method in subclasses to provide a custom template.
        """
        return self.template_name

    def get_visible(self) -> bool:
        """
        Determines if the block should be visible based on the request.
        Override this method in subclasses to implement custom visibility logic. This method
        runs after just before rendering the block therefore alternatively, you can change
        the `visible` attribute priory to rendering to change visibility late in the rendering logic.
        """
        return self.visible

    def get_context_data(self) -> dict:
        """
        Returns context data for the block.
        Override this method in subclasses to provide custom context data.
        """
        return {
            'block': self,
            'title': self.title,
            'style_classes': self.get_style_classes(),
            'width_classes': self.get_width_classes(),
            'src_url': self.src_url,
            'reload_freq': self.reload_freq,
        }

    def render(self):
        context_data = self.get_context_data()
        html = ""
        # an empty context_data means that the block is not visible
        if self.get_visible() or not (isinstance(context_data, dict) and context_data):
            with self.context.push(context_data):
                t = self.context.template.engine.get_template(self.get_template_name())
                html = t.render(self.context)
        return html
