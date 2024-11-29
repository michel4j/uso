from django.contrib import admin
from . import models

admin.site.register(models.Mode)
admin.site.register(models.ModeTag)
admin.site.register(models.ShiftConfig)
admin.site.register(models.Schedule)
