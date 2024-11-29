from django.contrib import admin
from . import models

# Register your models here.
admin.site.register(models.Publication)
admin.site.register(models.PublicationTag)
admin.site.register(models.Journal)
admin.site.register(models.Book)
admin.site.register(models.Patent)
admin.site.register(models.Article)
admin.site.register(models.FundingSource)
admin.site.register(models.SubjectArea)
admin.site.register(models.PDBDeposition)
