from django.contrib import admin

from beamlines import models


# Register your models here.
class WorkSpaceInline(admin.StackedInline):
    model = models.LabWorkSpace


class TagInline(admin.TabularInline):
    model = models.FacilityTag


class LabAdmin(admin.ModelAdmin):
    inlines = [
        WorkSpaceInline
    ]
    model = models.Lab


class FacilityAdmin(admin.ModelAdmin):
    inlines = [
        TagInline
    ]


admin.site.register(models.Facility, FacilityAdmin)
admin.site.register(models.Ancillary)
admin.site.register(models.FacilityTag)
admin.site.register(models.Lab, LabAdmin)
admin.site.register(models.LabWorkSpace)
