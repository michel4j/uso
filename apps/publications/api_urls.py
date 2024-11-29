from django.urls import re_path
from . import api_views
from . import models

urlpatterns = [
    re_path(r'^publications/(?P<facility>[\w-]+)/$', api_views.PublicationListAPI.as_view(model=models.Publication),
            name="api-publication-list"),
    re_path(r'^publications/(?P<facility>[\w-]+)/latest/$', api_views.RecentListAPI.as_view(model=models.Publication),
            name="api-recent-list"),
    re_path(r'^publications/(?P<category>[\w-]+)/(?P<facility>[\w-]+)/$', api_views.PublicationListAPI.as_view(),
            name="api-publication-category-list"),
    re_path(r'^categories/(?P<facility>[\w-]+)/$', api_views.CategoryListAPI.as_view(model=models.Publication),
            name="api-category-list"),
]
