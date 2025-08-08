from django.urls import path
from . import views

urlpatterns = [
    path('schedule/<int:pk>/modes/', views.ModeListAPI.as_view(), name='schedule-modes-api'),
    path('schedule/modes/', views.FacilityModeListAPI.as_view(), name='facility-modes-api'),
    path('<int:pk>/stats/', views.ModeStatsAPI.as_view(), name="mode-stats-api"),
    path('schedule/template/year/<int:slot>/', views.YearTemplate.as_view(), name="year-template-api"),
    path('schedule/template/month/<int:slot>/', views.MonthTemplate.as_view(), name="month-template-api"),
    path('schedule/template/week/<int:slot>/', views.WeekTemplate.as_view(), name="week-template-api"),
    path('schedule/template/cycle/<int:slot>/', views.CycleTemplate.as_view(), name="cycle-template-api"),
]