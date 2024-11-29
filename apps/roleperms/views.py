

from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.conf import settings

import itertools

ROLEPERMS_DEBUG = getattr(settings, "ROLEPERMS_DEBUG", False)


class LoginRequiredMixin(object):
    """
    Provides the ability to require an authenticated user for a view
    """

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class RolePermsViewMixin(object):
    """
    Provides the ability to  require a list of permissions.
    Add a context boolean variable 'admin' based on the view variable 'admin_permissions'.  
    To be used in template like {% if admin %}.
    
    Attributes:
    * admin_permissions: The list of permissions to recognize as admin.
    * allowed_permissions: Permissions allowed to access the view.
    * admin_roles: The list of roles to recognize as admin. 
    * allowed_roles: roles allowed to access the view.
    """
    admin_permissions = []  # list of permissions to recognize as admin
    admin_roles = []
    allowed_permissions = []  # list of permissions to recognize as admin
    allowed_roles = []

    def get_owners(self, obj):
        return []

    def check_owner(self, obj):
        owners = self.get_owners(obj)
        return False if not owners else (self.request.user in owners)

    def get_admin_permissions(self):
        return self.admin_permissions

    def get_admin_roles(self):
        return self.admin_roles

    def get_allowed_permissions(self):
        return self.allowed_permissions

    def get_allowed_roles(self):
        return self.allowed_roles

    def check_admin(self):
        admin_roles = set(self.get_admin_roles())
        admin_perms = set(self.get_admin_permissions())
        if admin_perms and admin_roles:
            return (len(admin_perms & self.request.user.get_all_permissions()) > 0) | (
                    len(admin_roles & set(self.request.user.get_all_roles())) > 0)
        elif admin_perms:
            return len(admin_perms & self.request.user.get_all_permissions()) > 0
        elif admin_roles:
            return len(admin_roles & set(self.request.user.get_all_roles())) > 0
        else:
            return False

    def check_allowed(self):
        allowed_roles = set(self.get_allowed_roles())
        allowed_perms = set(self.get_allowed_permissions())
        if allowed_perms and allowed_roles:
            return self.request.user.has_perms(allowed_perms) | (
                    len(set(allowed_roles) & set(self.request.user.get_all_roles())) > 0)
        elif allowed_perms:
            return self.request.user.has_perms(allowed_perms)
        elif allowed_roles:
            return (len(set(allowed_roles) & set(self.request.user.get_all_roles())) > 0)
        else:
            return True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['admin'] = self.check_admin()
        self.admin = context['admin']
        if context.get('object'):
            context['owner'] = self.check_owner(context['object'])
            self.owner = context['owner']
        return context

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        """
        Checks the permissions before dispatching the view otherwise return a 
        PermissionDenied exception.
        """
        if settings.DEBUG:
            print(('VIEW CLASS: \t{0}'.format(self.__class__)))

        if ROLEPERMS_DEBUG:
            print(('AUTH USER: \t{0}'.format(request.user)))
            print(('REQ.PERMS: \t{0}'.format(self.get_allowed_permissions())))
            print(('REQ.ROLES: \t{0}'.format(self.get_allowed_roles())))
            print(('ADM.PERMS: \t{0}'.format(set(itertools.chain(self.get_admin_permissions(), USO_ADMIN_PERMS)))))
            print(('ADM.ROLES: \t{0}'.format(set(itertools.chain(self.get_admin_roles(), USO_ADMIN_ROLES)))))
            print(('USER PERMS: \t{0}'.format(request.user.get_all_permissions())))
            print(('USER ROLES: \t{0}'.format(request.user.get_all_roles())))
            print(('ALLOWED: \t{0}'.format(self.check_allowed())))
            print(('ADMIN: \t{0}'.format(self.check_admin())))

        if self.check_allowed():
            return super().dispatch(request, *args, **kwargs)
        else:
            raise PermissionDenied


class OwnerRequiredMixin(RolePermsViewMixin):
    """
    Provides the ability to require ownership to access a SingleObject view.
    """

    def get_object(self, *args, **kwargs):
        obj = super().get_object(*args, **kwargs)
        if self.check_owner(obj):
            return obj
        else:
            raise PermissionDenied
