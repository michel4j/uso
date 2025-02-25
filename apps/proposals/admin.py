from django.contrib import admin

from . import models


class ReviewerAdmin(admin.ModelAdmin):
    list_display = ('user',)
    list_per_page = 100
    search_fields = ['user__first_name', 'user__email', 'user__last_name']
    ordering = ['user__last_name']


# Register your models here.
admin.site.register(models.Proposal)
admin.site.register(models.Submission)
admin.site.register(models.Review)
admin.site.register(models.Technique)
admin.site.register(models.FacilityConfig)
admin.site.register(models.ReviewTrack)
admin.site.register(models.ReviewCycle)
admin.site.register(models.Reviewer, ReviewerAdmin)
admin.site.register(models.ReviewType)
admin.site.register(models.ReviewStage)
