from django.urls import path
from . import views, models
from misc.views import ManageAttachments

urlpatterns = [
    path('proposals/', views.UserProposalList.as_view(), name="user-proposals"),
    path('proposals/<int:pk>/', views.ProposalDetail.as_view(), name='proposal-detail'),
    path('proposals/<int:pk>/edit/', views.EditProposal.as_view(), name='edit-proposal'),
    path('proposals/<int:pk>/clone/', views.CloneProposal.as_view(), name='clone-proposal'),
    path('proposals/<int:pk>/delete/', views.DeleteProposal.as_view(), name='delete-proposal'),
    path('proposals/<int:pk>/submit/', views.SubmitProposal.as_view(), name='submit-proposal'),

    path('proposals/<int:pk>/clarifications/new/', views.AskClarification.as_view(), name='request-proposal-clarification'),
    path('proposals/<int:ref>/clarifications/<int:pk>/response/', views.AnswerClarification.as_view(), name='proposal-clarification-response'),

    path('proposals/<int:pk>/clarifications/', views.ShowClarifications.as_view(), name='show-proposal-clarifications'),
    path('proposals/<int:pk>/attachments/manage/', ManageAttachments.as_view(reference_model=models.Proposal), name='proposal-attachments'),
    path('proposals/<int:pk>/attachments/<slug:slug>', ManageAttachments.as_view(reference_model=models.Proposal), name='get-proposal-attachment'),
    path('proposals/<int:pk>/attachments/', views.ShowAttachments.as_view(), name='show-proposal-attachments'),

    path('reviews/', views.UserReviewList.as_view(), name="user-reviews"),
    path('reviews/committee/', views.PRCAssignments.as_view(), name="personal-prc-reviews"),
    path('reviews/<int:pk>/', views.ReviewDetail.as_view(), name='review-detail'),
    path('reviews/<int:pk>/delete/', views.DeleteReview.as_view(), name='delete-review'),
    path('reviews/<int:pk>/edit/', views.EditReview.as_view(), name='edit-review'),
    path('reviews/<int:pk>/claim/', views.ClaimReview.as_view(), name='claim-review'),
    path('reviews/<int:pk>/print/', views.PrintReviewDoc.as_view(), name="print-review"),
]