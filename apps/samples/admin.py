from django.contrib import admin

from . import models


class StatementAdmin(admin.ModelAdmin):
    list_display = ['code', 'text']
    list_filter = ['created', 'modified']
    ordering = ['code']
    search_fields = ['code', 'text']


# Register your models here.
admin.site.register(models.Sample)
admin.site.register(models.Pictogram)
admin.site.register(models.Hazard)
admin.site.register(models.PStatement, StatementAdmin)
admin.site.register(models.HStatement, StatementAdmin)
admin.site.register(models.SafetyPermission)
admin.site.register(models.SafetyControl)
admin.site.register(models.UserRequirement)
admin.site.register(models.HazardousSubstance)
