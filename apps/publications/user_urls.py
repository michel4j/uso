from django.urls import path
from . import views

urlpatterns = [
    path('publications/', views.UserPublicationList.as_view(), name='user-publication-list'),
    path('publications/matches/', views.ClaimPublicationList.as_view(), name='claim-publication-list'),
    path('publications/add/<int:pk>/', views.ClaimPublication.as_view(), name='claim-publication'),
    path('publications/remove/<int:pk>/', views.UnclaimPublication.as_view(), name='unclaim-publication'),
]
