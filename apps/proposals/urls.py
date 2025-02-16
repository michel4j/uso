from django.urls import path

from . import models
from . import views
from misc.views import ManageAttachments

urlpatterns = [
    path('proposals/', views.UserProposalList.as_view(), name="proposal-list"),
    path('proposals/statistics/', views.Statistics.as_view(), name="proposal-stats"),
    path('proposals/statistics/data/', views.StatsDataAPI.as_view(), name="proposal-stats-api"),
    path('proposals/inprogress/', views.ProposalList.as_view(), name="proposals-inprogress"),
    path('proposals/new/', views.CreateProposal.as_view(), name="create-proposal"),

    path('submissions/', views.SubmissionList.as_view(), name='submission-list'),
    path('submissions/<int:pk>/', views.SubmissionDetail.as_view(), name='submission-detail'),
    path('submissions/<int:pk>/adjust/', views.AddScoreAdjustment.as_view(), name='adjust-submission-score'),
    path('submissions/<int:pk>/unadjust/', views.DeleteAdjustment.as_view(), name='remove-score-adjustment'),
    path('submissions/<int:pk>/comments/', views.UpdateReviewComments.as_view(), name='edit-submission-comments'),
    path('submission/<int:pk>/assign/', views.AddReviewAssignment.as_view(), name='add-reviewer-assignment'),

    path('reviews/', views.ReviewList.as_view(), name='review-list'),
    path('reviews/<int:pk>/compatibility/', views.ReviewCompatibility.as_view(), name="show-compatibility"),

    path('facilities/<int:pk>/configs/new/', views.AddFacilityConfig.as_view(), name='add-facility-config'),
    path('facilities/<int:pk>/configs/<int:config>/edit/', views.AddFacilityConfig.as_view(), name='edit-facility-config'),
    path('facilities/configs/<int:pk>/edit/', views.EditConfig.as_view(), name='edit-facility-config'),
    path('facilities/configs/<int:pk>/delete/', views.DeleteConfig.as_view(), name='delete-facility-config'),
    path('facilities/<int:pk>/submissions/', views.BeamlineSubmissionList.as_view(), name='beamline-submissions'),

    path('cycles/', views.ReviewCycleList.as_view(), name="review-cycle-list"),
    path('cycles/<int:pk>/', views.ReviewCycleDetail.as_view(), name="review-cycle-detail"),
    path('cycles/<int:pk>/add/', views.AddReviewCycles.as_view(), name="add-review-cycles"),
    path('cycles/<int:pk>/edit/', views.EditReviewCycle.as_view(), name="edit-review-cycle"),
    path('review-tracks/<int:pk>/edit/', views.EditReviewTrack.as_view(), name="edit-review-track"),
    path('cycles/<int:pk>/assign/<int:track>/', views.AssignReviewers.as_view(), name="assign-reviewers"),
    path('cycles/<int:pk>/start-reviews/', views.StartReviews.as_view(), name="start-reviews"),
    path('cycles/<int:cycle>/assigned/<int:track>/', views.AssignedSubmissionList.as_view(), name="assigned-reviewers"),
    path('cycles/<int:cycle>/committee/<int:pk>/', views.ReviewerAssignments.as_view(), name="prc-reviews"),
    path('cycles/<int:cycle>/committee/<str:track>/', views.PRCList.as_view(), name="prc-members"),
    path('cycles/<int:cycle>/<str:track>/evaluation/', views.ReviewEvaluationList.as_view(), name='review-evaluation'),
    path('cycles/<int:cycle>/add-reviewer/<int:pk>/', views.AddReviewerAPI.as_view(), name="add-cycle-reviewer"),
    path('cycles/<int:cycle>/remove-reviewer/<int:pk>/', views.RemoveReviewerAPI.as_view(), name="del-cycle-reviewer"),
    path('cycles/<int:pk>/reviewers/', views.AddReviewerList.as_view(), name="change-cycle-reviewers"),

    path('reviewers/', views.ReviewerList.as_view(), name="reviewer-list"),
    path('reviewers/<int:pk>/edit/', views.EditReviewerProfile.as_view(), name="edit-reviewer-profile"),
    path('reviewers/edit/', views.EditReviewerProfile.as_view(), name="edit-reviewer-profile"),
    path('reviewers/<int:pk>/opt-out/', views.ReviewerOptOut.as_view(), name='reviewer-opt-out'),



]