from django.urls import path

from . import views

urlpatterns = [
    path('feedback/', views.UserFeedback.as_view(), name='user-feedback'),
]