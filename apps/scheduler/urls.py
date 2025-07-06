from django.urls import path
from . import views

urlpatterns = [
    path('schedules/', views.ScheduleListView.as_view(), name="schedule-list"),
    path('schedules/calendar', views.Calendar.as_view(), name="schedule-calendar"),
    path('schedules/calendar/<str:month>/', views.Calendar.as_view(), name="schedule-calendar-month"),
    path('schedules/calendar/<int:year>/', views.Calendar.as_view(), name="schedule-calendar-year"),

    path('schedules/<int:pk>/modes/<str:date>/', views.ModeEditor.as_view(), name="schedule-modes-edit"),
    path('schedules/<int:pk>/overlay/', views.ModeEditor.as_view(), name="schedule-modes-edit"),
    path('schedules/<int:pk>/switch/<str:state>/', views.PromoteSchedule.as_view(), name="switch-schedule"),

    path('mode-types/', views.ModeTypeList.as_view(), name="mode-type-list"),
    path('mode-types/<int:pk>/edit/', views.EditModeType.as_view(), name="edit-mode-type"),
    path('mode-types/<int:pk>/delete/', views.DeleteModeType.as_view(), name="delete-mode-type"),
    path('mode-types/create/', views.AddModeType.as_view(), name="add-mode-type"),
]
