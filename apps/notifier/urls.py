from django.urls import re_path, path

from . import views

urlpatterns = [
    path('messages/', views.NotificationList.as_view(), name="admin-notification-list"),
    path('messages/<int:pk>/', views.NotificationDetail.as_view(), name='notification-admin-detail'),
    path('notifications/', views.MessageTemplateList.as_view(), name='template-list'),
    path('notifications/<int:pk>/edit/', views.EditTemplate.as_view(), name='edit-template-modal'),
    path('notifications/new/', views.CreateTemplate.as_view(), name='add-template-modal'),
    path('notifications/<int:pk>/delete/', views.CreateTemplate.as_view(), name='delete-template-modal'),
]
