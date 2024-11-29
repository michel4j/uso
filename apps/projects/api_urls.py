from django.urls import path

from . import views

urlpatterns = [
    path("schedule/beamtime/<str:fac>/<int:pk>/", views.BeamTimeAPI.as_view(), name='schedule-beamtime-api'),
    path("schedule/beamtime/<str:fac>/<int:pk>/stats/", views.BeamtimeStatsAPI.as_view(), name="schedule-beamtime-stats-api"),
    path("schedule/beamtime/<str:fac>/", views.BeamTimeListAPI.as_view(), name='beamtime-schedule-api'),
    path("schedule/request/<int:pk>/<str:fac>/", views.RequestPreferencesAPI.as_view(), name='schedule-request-api'),
    path("schedule/project/<int:pk>/", views.ProjectScheduleAPI.as_view(), name='project-schedule-api'),
]