# Register your models here.
from django.contrib import admin

from . import models

admin.site.register(models.Agreement)
admin.site.register(models.Acceptance)