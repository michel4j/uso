from django.urls import path

from . import views


urlpatterns = [
    path('surveys/feedback/', views.UserFeedback.as_view(), name='user-feedback'),
]