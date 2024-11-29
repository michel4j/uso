from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r'^attachments/(?P<slug>\w+)/del$', views.DeleteAttachment.as_view(), name='del-attachment'),
    re_path(r'^ping/', views.Ping.as_view(), name='ping-server')
]
