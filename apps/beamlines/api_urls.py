from django.urls import path

from beamlines import views

urlpatterns = [
    path('beamlines/info/', views.FacilityDetails.as_view(), name='beamline-info-root'),   # Root URL for beamline info
    path('beamlines/info/<int:pk>/', views.FacilityDetails.as_view(), name='beamline-info'),

    path('schedule/support/<slug:fac>/<int:pk>/', views.UserSupportAPI.as_view(), name='schedule-support-api'),
    path(
        'schedule/support/<slug:fac>/<int:pk>/stats/', views.UserSupportStatsAPI.as_view(),
        name='schedule-support-stats-api'
    ),
    path('schedule/support/<slug:fac>/', views.UserSupportListAPI.as_view(), name='support-schedule-api'),
]
