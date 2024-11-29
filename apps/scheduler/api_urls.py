from django.urls import re_path
from . import views

urlpatterns = [
    re_path(r'^schedule/(?P<pk>\d+)/modes/$', views.ModeListAPI.as_view(), name='schedule-modes-api'),
    re_path(r'^schedule/modes/$', views.FacilityModeListAPI.as_view(), name='facility-modes-api'),
    re_path(r'^(?P<pk>\d+)/stats/$', views.ModeStatsAPI.as_view(), name="mode-stats-api"),
    re_path(r'^schedule/template/year/(?P<slot>\d+)?$', views.YearTemplate.as_view(), name="year-template-api"),
    re_path(r'^schedule/template/month/(?P<slot>\d+)?$', views.MonthTemplate.as_view(), name="month-template-api"),
    re_path(r'^schedule/template/week/(?P<slot>\d+)?$', views.WeekTemplate.as_view(), name="week-template-api"),
    re_path(r'^schedule/template/cycle/(?P<slot>\d+)?$', views.CycleTemplate.as_view(), name="cycle-template-api"),
]
