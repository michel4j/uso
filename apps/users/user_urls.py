from django.urls import re_path
from django.contrib.auth.views import LoginView, LogoutView
from django.views import generic
from django.views.decorators.cache import cache_page

from . import views

urlpatterns = [
    re_path(r'^$', views.UserDetailView.as_view(), name="user-dashboard"),
    re_path(r'^profile/edit/$', views.UpdateUserProfile.as_view(), name="edit-my-profile"),
    re_path(r'^profile/sync/$', views.SyncProfile.as_view(), name="sync-profile"),
    re_path(r'^profile/$', views.UserDetailView.as_view(template_name='users/user_personal.html'), name="view-my-profile"),

]
