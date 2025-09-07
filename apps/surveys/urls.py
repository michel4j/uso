from django.urls import path

from . import views


urlpatterns = [
    path('surveys/submit-feedback/', views.UserFeedback.as_view(), name='user-feedback'),
    path('surveys/feedbacks/', views.AdminFeedbackList.as_view(), name='admin-feedback-list'),
    path('surveys/feedbacks/<int:pk>/', views.FeedbackDetail.as_view(), name='feedback-detail'),
    path('surveys/facility-feedbacks/<slug:facility>/', views.FacilityFeedbackList.as_view(), name='facility-feedback-list'),
    path('surveys/cycle-feedbacks/<int:cycle>/', views.CycleFeedbackList.as_view(), name='cycle-feedback-list'),
]