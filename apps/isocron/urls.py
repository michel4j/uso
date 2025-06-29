from django.urls import path
from . import autodiscover
from . import views

autodiscover()

urlpatterns = [
    path('background-tasks/', views.TaskList.as_view(), name='task-list'),
    path('background-tasks/<int:pk>/', views.TaskDetail.as_view(), name='task-detail'),
    path('background-tasks/<int:pk>/edit/', views.TaskDetail.as_view(), name='task-edit'),
    path('background-tasks/<int:pk>/run/', views.TaskDetail.as_view(), name='task-run'),
]