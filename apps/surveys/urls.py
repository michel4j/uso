from django.urls import path

from . import views

urlpatterns = [
    path('surveys/cycle/<int:pk>/', views.ReviewCycleFeedback.as_view(), name="review-cycle-feedback"),
]
