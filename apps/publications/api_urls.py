from django.urls import path
from . import api_views
from . import models

urlpatterns = [
    path('publications/<str:facility>/', api_views.PublicationListAPI.as_view(model=models.Publication),
         name="api-publication-list"),
    path('publications/<str:facility>/latest/', api_views.RecentListAPI.as_view(model=models.Publication),
         name="api-recent-list"),
    path('publications/<str:category>/<str:facility>/', api_views.PublicationListAPI.as_view(),
         name="api-publication-category-list"),
    path('categories/<str:facility>/', api_views.CategoryListAPI.as_view(model=models.Publication),
         name="api-category-list"),
]