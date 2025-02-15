from django.contrib import admin

from . import models

# Register your models here.
admin.site.register(models.Project)
admin.site.register(models.Allocation)
admin.site.register(models.Material)
admin.site.register(models.Session)
admin.site.register(models.AllocationRequest)
admin.site.register(models.ProjectSample)
