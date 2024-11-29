from django.contrib.auth.models import PermissionsMixin
from django.conf import settings


class RolePermsUserMixin(PermissionsMixin):
    """
    A mixin class that adds the methods necessary to support
    RolePerms extended Permission framework.
    """

    class Meta:
        abstract = True

    @property
    def is_superuser(self):
        """Override is_superuser with developer admin"""
        if self.pk:
            return self.has_roles(getattr(settings, "USO_ADMIN_ROLES", ['XXX_XXX_XXX']))
        else:
            return False

    @is_superuser.setter
    def is_superuser(self, val):
        """Ignore value from database"""
        return

    def natural_key(self):
        return (self.username,)

    def get_all_permissions(self):
        raise NotImplementedError('Must redefine get_all_permissions in the subclass')

    def get_all_roles(self):
        raise NotImplementedError('Must redefine get_all_roles in the subclass')

    def has_perm(self, perm, obj=None):
        """
        Returns True if the user has the specified permission. For consistency,
        the obj argument is provided to mirror the has_perms of auth.PermissionsMixin
        it is not used at the moment.
        """
        return (perm in self.get_all_permissions()) or self.is_superuser

    def has_role(self, role, obj=None):
        """
        Returns True if the user has the specified role. For consistency,
        the obj argument is provided to mirror the has_perms of auth.PermissionsMixin
        it is not used at the moment.
        """
        return role in self.get_all_roles()

    def has_perms(self, perm_list, obj=None):
        """
        Returns True if the user has any of the specified permissions. For consistency,
        the obj argument is provided to mirror the has_perms of auth.PermissionsMixin
        it is not used at the moment.
        This method changes the behaviour of standard Django auth.PermissionsMixin in that
        it returns True based on ANY. Django returns true only if user has ALL permissions
        """
        return len(perm_list) == 0 or (len(set(perm_list) & self.get_all_permissions()) > 0)

    def has_all_perms(self, perm_list, obj=None):
        """
        Returns True if the user has all the specified permissions.
        """
        return self.get_all_permissions() >= set(perm_list)

    def has_roles(self, role_list, obj=None):
        """
        Returns True if the user has any of the specified roles. For consistency,
        the obj argument is provided to mirror the has_perms of auth.PermissionsMixin
        it is not used at the moment.
        """
        return len(role_list) == 0 or (len(set(role_list) & self.get_all_roles()) > 0)

    def has_all_roles(self, role_list, obj=None):
        """
        Returns True if the user has all the specified roles. For consistency,
        the obj argument is provided to mirror the has_perms of auth.PermissionsMixin
        it is not used at the moment.
        """
        return self.get_all_roles() >= set(role_list)

    def has_module_perms(self, module):
        return self.has_perm(module)

    def get_group_permissions(self, obj=None):
        # Not used so return an empty set
        return set()
