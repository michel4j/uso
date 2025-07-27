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

    path('techniques/matrix/', views.TechniquesMatrix.as_view(), name="techniques-matrix"),
    path('techniques/', views.TechniqueList.as_view(), name="technique-list"),
    path('techniques/<int:pk>/edit/', views.EditTechnique.as_view(), name="edit-technique"),
    path('techniques/<int:pk>/delete/', views.DeleteTechnique.as_view(), name="delete-technique"),
    path('techniques/new/', views.AddTechnique.as_view(), name="add-technique"),


    path('submissions/', views.SubmissionList.as_view(), name='submission-list'),
    path('submissions/cycle/<int:cycle>/', views.CycleSubmissionList.as_view(), name='cycle-submission-list'),
    path('submissions/cycle/<int:cycle>/<slug:track>/', views.TrackSubmissionList.as_view(), name='track-submission-list'),
    path('submissions/<int:pk>/', views.SubmissionDetail.as_view(), name='submission-detail'),
    path('submissions/<int:pk>/comments/', views.UpdateReviewComments.as_view(), name='edit-submission-comments'),
    path('submission/<int:pk>/assign/<int:stage>/', views.AddReviewAssignment.as_view(), name='add-reviewer-assignment'),

    path('reviews/', views.ReviewList.as_view(), name='review-list'),
    path('reviews/<int:cycle>/<int:stage>/', views.StageReviewList.as_view(), name='stage-review-list'),
    path('reviews/<int:pk>/compatibility/', views.ReviewCompatibility.as_view(), name="show-compatibility"),

    path('facilities/<slug:slug>/configs/new/', views.AddFacilityConfig.as_view(), name='add-facility-config'),
    path('facilities/configs/<int:pk>/edit/', views.EditConfig.as_view(), name='edit-facility-config'),
    path('facilities/configs/<int:pk>/delete/', views.DeleteConfig.as_view(), name='delete-facility-config'),
    path('facilities/<slug:slug>/pools/', views.EditFacilityPools.as_view(), name='edit-facility-pools'),
    path('facilities/<slug:slug>/submissions/', views.FacilitySubmissionList.as_view(), name='facility-submissions'),
    path('facilities/<slug:slug>/submissions/<int:cycle>/', views.FacilitySubmissionList.as_view(), name='facility-cycle-submissions'),
    path('facilities/<slug:slug>/proposals/', views.FacilityDraftProposals.as_view(), name='facility-proposals'),

    path('cycles/', views.ReviewCycleList.as_view(), name="review-cycle-list"),
    path('cycles/<int:pk>/', views.ReviewCycleDetail.as_view(), name="review-cycle-detail"),
    path('cycles/<int:pk>/add/', views.AddReviewCycles.as_view(), name="add-review-cycles"),
    path('cycles/<int:pk>/edit/', views.EditReviewCycle.as_view(), name="edit-review-cycle"),

    path('cycles/<int:pk>/assign/<int:stage>/', views.AssignReviewers.as_view(), name="assign-reviewers"),
    path('cycles/<int:cycle>/start-reviews/<int:pk>/', views.StartReviews.as_view(), name="start-reviews"),
    path('cycles/<int:cycle>/assigned/<int:stage>/', views.AssignedSubmissionList.as_view(), name="assigned-reviewers"),
    path('cycles/<int:cycle>/committee/<int:pk>/', views.ReviewerAssignments.as_view(), name="prc-reviews"),
    path('cycles/<int:cycle>/committee/<str:track>/', views.PRCList.as_view(), name="prc-members"),
    path('cycles/<int:cycle>/<str:track>/evaluation/', views.ReviewEvaluationList.as_view(), name='review-evaluation'),

    path('tracks/', views.ReviewTrackList.as_view(), name="review-track-list"),
    path('tracks/new/', views.AddReviewTrack.as_view(), name="add-review-track"),
    path('tracks/<int:pk>/edit/', views.EditReviewTrack.as_view(), name="edit-review-track"),
    path('tracks/<int:pk>/delete/', views.DeleteReviewTrack.as_view(), name="delete-review-track"),
    path('tracks/<slug:track>/stages/add/', views.AddReviewStage.as_view(), name="add-review-stage"),
    path('tracks/<slug:track>/stages/<int:pk>/edit/', views.EditReviewStage.as_view(), name="edit-review-stage"),
    path('tracks/<slug:track>/stages/<int:pk>/delete/', views.DeleteReviewStage.as_view(), name="delete-review-stage"),

    path('reviewers/', views.ReviewerList.as_view(), name="reviewer-list"),
    path('reviewers/<int:pk>/edit/', views.EditReviewerProfile.as_view(), name="edit-reviewer-profile"),
    path('reviewers/edit/', views.EditReviewerProfile.as_view(), name="edit-reviewer-profile"),
    path('reviewers/<int:pk>/opt-out/', views.ReviewerOptOut.as_view(), name='reviewer-opt-out'),

    path('review-types/', views.ReviewTypeList.as_view(), name="review-type-list"),
    path('review-types/<int:pk>/edit/', views.EditReviewType.as_view(), name="edit-review-type"),
    path('review-types/<int:pk>/delete/', views.DeleteReviewType.as_view(), name="delete-review-type"),
    path('review-types/new/', views.AddReviewType.as_view(), name="add-review-type"),

    path('access-pools/', views.AccessPoolList.as_view(), name="access-pool-list"),
    path('access-pools/<int:pk>/edit/', views.EditAccessPool.as_view(), name="edit-access-pool"),
    path('access-pools/<int:pk>/delete/', views.DeleteAccessPool.as_view(), name="delete-access-pool"),
    path('access-pools/new/', views.AddAccessPool.as_view(), name="add-access-pool"),

    path('cycle-types/', views.CycleTypeList.as_view(), name="cycle-type-list"),
    path('cycle-types/<int:pk>/edit/', views.EditCycleType.as_view(), name="edit-cycle-type"),
    path('cycle-types/<int:pk>/delete/', views.DeleteCycleType.as_view(),  name="delete-cycle-type"),
    path('cycle-types/new/', views.AddCycleType.as_view(), name="add-cycle-type"),

]