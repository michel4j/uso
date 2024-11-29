from django.urls import re_path
from proposals import views

urlpatterns = [
    # field urls
    re_path(r'^proposals/facility-options/$', views.FacilityOptions.as_view(), name='techniques-beamlines'),
    re_path(r'^proposals/reviewer-options/$', views.ReviewerOptions.as_view(), name='reviewer-options'),
    re_path(r'^proposals/cycle-info/(:?(?P<pk>\d+)/)?$', views.CycleInfo.as_view()),
    re_path(r'^proposals/cycle-info/$', views.CycleInfo.as_view(), name='cycle-info'),
]
