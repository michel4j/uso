from django.urls import path
from . import views
from django.views.decorators.cache import cache_page

urlpatterns = [
    path('publications/', views.PublicationList.as_view(), name='publication-list'),
    path('publications/new/', views.PublicationWizard.as_view(), name='add-publication'),
    path('publications/keywords/', views.KeywordCloud.as_view(), name='keyword-cloud'),
    path('publications/admin/', views.PublicationAdminList.as_view(), name='publication-admin-list'),
    path('publications/admin/<int:pk>/delete/', views.PublicationDelete.as_view(), name='delete-publication'),
    path('publications/review/', views.PublicationReviewList.as_view(), name='publication-review-list'),
    path('publications/review/<int:pk>/', views.PublicationReview.as_view(), name='review-publication'),

    path('publications/funders/', views.FunderList.as_view(), name='funder-list'),

    path('publications/topics/', views.SubjectAreaList.as_view(), name='subject-area-list'),
    path('publications/topics/<int:pk>/', views.EditSubjectArea.as_view(), name='edit-subject-area'),

    path('publications/focus/', views.FocusAreaList.as_view(), name='focus-area-list'),
    path('publications/focus/<int:pk>/', views.EditFocusArea.as_view(), name='edit-focus-area'),
    path('publications/focus/<int:pk>/delete/', views.DeleteFocusArea.as_view(), name='delete-focus-area'),
    path('publications/focus/add/', views.CreateFocusArea.as_view(), name='add-focus-area'),


    path('publications/years/<int:year>/', views.PublicationList.as_view(), name='year-publication-list'),
    path('publications/beamline/<str:beamline>/', views.PublicationList.as_view(), name='facility-publication-list'),
    path('publications/years/<int:year>-<int:end_year>/', views.PublicationList.as_view(), name='years-publication-list'),
    path('publications/beamline/<str:beamline>/<int:year>/', views.PublicationList.as_view()),
    path('publications/beamline/<str:beamline>/<int:year>-<int:end_year>/', views.PublicationList.as_view()),


]