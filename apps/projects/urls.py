from django.urls import path

from . import models
from . import views


urlpatterns = [
    path('projects/', views.ProjectList.as_view(), name="project-list"),
    path('projects/new/', views.CreateProject.as_view(), name="create-project"),

    path('projects/reports/', views.Statistics.as_view(), name="project-stats"),

    path('allocations/<int:pk>/request/shift/new/', views.CreateShiftRequest.as_view(), name="create-shift-request"),
    path('allocations/request/shift/<int:pk>/edit/', views.EditShiftRequest.as_view(), name='edit-shift-request'),
    path('allocations/request/', views.AllocRequestList.as_view(), name="alloc-request-list"),
    path('allocations/request/shift/<int:pk>/<int:cycle>/', views.ShiftRequestList.as_view(), name='shift-request-list'),
    path('allocations/<int:pk>/decline/', views.DeclineAllocation.as_view(), name="decline-alloc"),
    path('allocations/cycles/<int:pk>/<str:fac>/', views.AllocateBeamtime.as_view(), name="allocate-review-cycle"),
    path('allocations/<int:pk>/edit/', views.EditAllocation.as_view(), name='edit-allocation'),

    path('facilities/<int:fac>/projects/<int:cycle>/', views.BeamlineProjectList.as_view(), name="beamline-projects"),
    path('facilities/<int:fac>/projects/', views.BeamlineProjectList.as_view(), name="beamline-projects"),

    path('materials/', views.MaterialList.as_view(), name='material-list'),
    path('materials/<int:pk>/', views.MaterialDetail.as_view(), name='material-detail'),

    path('beamtime/<str:fac>/<int:pk>/', views.ScheduleBeamTime.as_view(), name="schedule-beamtime"),
    path('beamtime/<str:fac>/', views.BeamlineSchedule.as_view(), name="beamline-schedule"),
    path('beamtime/<str:fac>/<str:date>/', views.BeamlineSchedule.as_view(), name="beamline-schedule-date"),

    path('sessions/', views.SessionList.as_view(), name='session-list'),
    path('sessions/<int:pk>/', views.SessionDetail.as_view(), name='session-detail'),
    path('sessions/<int:pk>/delete/', views.DeleteSession.as_view(), name='delete-session'),
    path('sessions/<int:pk>/stop/', views.TerminateSession.as_view(), name='terminate-session'),

    path('sessions/<int:pk>/handover/<str:fac>/', views.SessionHandOver.as_view(), name="session-handover"),
    path('sessions/<int:pk>/extend/', views.SessionExtend.as_view(), name="session-extend"),
    path('sessions/<int:pk>/signon/', views.SessionSignOn.as_view(), name='session-signon'),
    path('sessions/<int:pk>/signoff/', views.SessionSignOff.as_view(), name='session-signoff'),
    path('lab-sessions/', views.LabSessionList.as_view(), name='lab-permit-list'),
    path('lab-sessions/<int:pk>/signon/', views.LabSignOn.as_view(), name='lab-signon'),
    path('lab-sessions/<int:pk>/signoff/', views.LabSignOff.as_view(), name='lab-signoff'),
    path('lab-sessions/<int:pk>/cancel/', views.CancelLabSession.as_view(), name='cancel-lab-session'),
    path('lab-sessions/<int:pk>/', views.LabPermit.as_view(), name='lab-permit'),

    path('reservations/<int:cycle>/<str:fac>/<str:pool>/', views.EditReservation.as_view(), name='edit-reservation'),
    path('reservations/<int:cycle>/<str:fac>/', views.EditReservation.as_view(), name='edit-reservation'),

]