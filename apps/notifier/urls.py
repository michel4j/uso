from django.urls import re_path, path

from . import views

urlpatterns = [
    path('', views.NotificationList.as_view(), name="notification-list"),
    path('<int:pk>/', views.NotificationDetail.as_view(), name='notification-detail'),
    path('templates/', views.MessageTemplateList.as_view(), name='template-list'),
    path('templates/<int:pk>/edit/', views.EditTemplate.as_view(), name='edit-message-template'),
    path('templates/add/', views.CreateTemplate.as_view(), name='add-message-template'),
    path('templates/<int:pk>/delete/', views.DeleteTemplate.as_view(), name='delete-message-template'),
]
