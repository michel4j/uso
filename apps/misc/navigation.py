from collections import defaultdict

from misc.utils import load
from django.conf import settings


USO_ADMIN_ROLES = getattr(settings, 'USO_ADMIN_ROLES', [])
USO_ADMIN_PERMS = getattr(settings, 'USO_ADMIN_PERMS', [])


def autodiscover():
    load('navs')


def _get_name(cls):
    return ".".join([cls.__module__.split('.')[0], cls.__name__])


class NavMeta(type):
    def __init__(cls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(cls, 'plugins'):
            cls.plugins = {}

        if cls.label:
            cls.name = _get_name(cls)
            if cls.parent and not isinstance(cls.parent, str):
                cls.parent = _get_name(cls.parent)

            if cls.weight < 0:
                cls.weights[cls.parent] += 1
                cls.weight = cls.weights[cls.parent]

            if cls.parent:
                cls.children[cls.parent].add(cls)
            else:
                cls.plugins[cls.name] = cls

    def get_menus(cls):
        autodiscover()
        return [m() for m in list(cls.plugins.values())]


class BaseNav(object, metaclass=NavMeta):
    label = ''
    parent = None
    styles = ""
    section = None
    icon = '<i class=""></i>'
    url = '#0'
    weight = -1
    roles = []
    permissions = []
    separator = False
    weights = defaultdict(int)
    children = defaultdict(set)

    def get_url(self):
        return self.url

    def allowed(self, request):
        if not request.user.is_authenticated:
            return False

        if self.roles and self.permissions:
            roles = self.roles + USO_ADMIN_ROLES
            perms = self.permissions + USO_ADMIN_PERMS
            return request.user.has_any_role(*roles) or request.user.has_any_perm(*perms)
        elif self.roles:
            roles = self.roles + USO_ADMIN_ROLES
            return request.user.has_any_role(*roles)
        elif self.permissions:
            perms = self.permissions + USO_ADMIN_PERMS
            return request.user.has_any_perm(*perms)
        else:
            return True

    def sub_menu(self, request):
        entries = [m() for m in self.children[self.name]]
        return sorted([x for x in entries if x.allowed(request)], key=lambda x: x.weight)

    def active(self, request):
        if request.path.startswith(self.url):
            return ' active '
        else:
            return ''


class RawNav(object):
    def __init__(self, **kwargs):
        self.label = kwargs.get('label', '')
        self.parent = kwargs.get('parent', None)
        self.styles = kwargs.get('styles', '')
        self.icon = kwargs.get('icon', '')
        self.url = kwargs.get('url', '')
        self.roles = kwargs.get('roles', [])
        self.permissions = kwargs.get('permissions', [])
        self.separator = kwargs.get('separator', False)

    def get_url(self):
        return self.url

    def allowed(self, request):
        if self.roles and self.permissions:
            roles = self.roles + USO_ADMIN_ROLES
            perms = self.permissions + USO_ADMIN_PERMS
            return request.user.has_any_role(*roles) or request.user.has_any_perm(*perms)
        elif self.roles:
            roles = self.roles + USO_ADMIN_ROLES
            return request.user.has_any_role(*roles)
        elif self.permissions:
            perms = self.permissions + USO_ADMIN_PERMS
            return request.user.has_any_perm(*perms)
        else:
            return True

    def active(self, request):
        if request.path.startswith(self.url):
            return ' active '
        else:
            return ''
