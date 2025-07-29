from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r'^$', views.UserDetailView.as_view(), name="user-dashboard"),
    re_path(r'^profile/edit/$', views.UpdateUserProfile.as_view(), name="edit-my-profile"),
    re_path(r'^profile/sync/$', views.SyncProfile.as_view(), name="sync-profile"),
]
