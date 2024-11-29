from django.urls import path

from . import views

urlpatterns = [
    path('messages/', views.UserNotificationList.as_view(), name="notification-list"),
    path('messages/<int:pk>/', views.UserNotificationDetail.as_view(), name='notification-detail'),
]
