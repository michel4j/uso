from django.contrib import admin

from users import models


class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'first_name', 'last_name', 'email', 'institution', 'classification', 'created')
    list_per_page = 100
    search_fields = ['last_name', 'username', 'first_name', 'other_names', 'email', 'alt_email']
    list_filter = ['created', 'modified', 'classification']
    ordering = ['last_name']
    fields = [
        'title', 'username', 'first_name', 'last_name', 'other_names', 'email', 'alt_email', 'address', 'institution',
        'research_field', 'classification', 'preferred_name', 'emergency_contact', 'emergency_phone',
        'roles', 'permissions'
    ]


class InstitutionAdmin(admin.ModelAdmin):
    list_display = ('name', 'sector', 'location', 'state', 'created')
    list_per_page = 100
    search_fields = ['name', 'location', 'state']
    list_filter = ['sector']
    ordering = ['name']


class SecureLinkAdmin(admin.ModelAdmin):
    list_display = ('hash', 'user', 'created')
    list_filter = ['created', 'modified']
    list_per_page = 100


admin.site.register(models.User, UserAdmin)
admin.site.register(models.Registration)
admin.site.register(models.Institution, InstitutionAdmin)
admin.site.register(models.Address)
admin.site.register(models.SecureLink, SecureLinkAdmin)
