from django.urls import path

from . import views

urlpatterns = [
    # field urls
    path('institution/', views.InstitutionDetail.as_view(), name="institution-detail"),
    path('institution/search/', views.InstitutionSearch.as_view(), name="institution-search"),
    path('institution/entries/', views.InstitutionInfo.as_view(), name="institution-entries"),
    path('regions/', views.CountryRegions.as_view(), name="country-regions"),
]
