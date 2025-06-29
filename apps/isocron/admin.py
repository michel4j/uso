from django.contrib import admin

from . import models

# Register your models here.
admin.site.register(models.TaskLog)
admin.site.register(models.BackgroundTask)
