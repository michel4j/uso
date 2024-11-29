from django.urls import re_path

from . import views

urlpatterns = [
    # field urls
    re_path(r'^institution/$', views.InstitutionDetail.as_view(), name="institution-detail"),
    re_path(r'^institution/search/$', views.InstitutionSearch.as_view(), name="institution-search"),
    re_path(r'^institution/names/$', views.InstitutionNames.as_view(), name="institution-names"),
]
