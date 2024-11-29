from django.urls import path

from beamlines import views

urlpatterns = [
    # field urls

    path('beamlines/tags/', views.FacilityTags.as_view(), name='facility-tags'),
    path('beamlines/tags/<int:pk>/<str:field_name>/', views.FacilityTags.as_view(), name='facility-tags'),

    path('beamlines/info/', views.FacilityDetails.as_view(), name='beamline-info'),
    path('beamlines/info/<int:pk>/', views.FacilityDetails.as_view(), name='beamline-info'),

    path('schedule/support/<str:fac>/<int:pk>/', views.UserSupportAPI.as_view(), name='schedule-support-api'),
    path(
        'schedule/support/<str:fac>/<int:pk>/stats/', views.UserSupportStatsAPI.as_view(),
        name='schedule-support-stats-api'
    ),
    path('schedule/support/<str:fac>/', views.UserSupportListAPI.as_view(), name='support-schedule-api'),
]
