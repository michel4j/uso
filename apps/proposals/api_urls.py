from django.urls import re_path, path
from proposals import views

urlpatterns = [
    # field urls
    path('proposals/facility-options/', views.FacilityOptions.as_view(), name='techniques-beamlines'),
    path('proposals/reviewer-options/', views.ReviewerOptions.as_view(), name='reviewer-options'),
    path('proposals/cycle-info/<int:pk>/', views.CycleInfo.as_view(), name='cycle-info'),
]
