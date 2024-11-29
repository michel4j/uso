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

    path('publications/years/<int:year>/', cache_page(60 * 0)(views.PublicationList.as_view()), name='publication-list'),
    path('publications/<str:beamline>/', cache_page(60 * 0)(views.PublicationList.as_view()), name='publication-list'),
    path('publications/years/<int:year>-<int:end_year>/', cache_page(60 * 0)(views.PublicationList.as_view()), name='publication-list'),
    path('publications/<str:beamline>/<int:year>/', cache_page(60 * 0)(views.PublicationList.as_view()), name='publication-list'),
    path('publications/<str:beamline>/<int:year>-<int:end_year>/', cache_page(60 * 0)(views.PublicationList.as_view()), name='publication-list'),

    path('reports/publication/summary/', views.ActivitySummary.as_view(), name='activity-summary'),
    path('reports/publication/quality/', views.QualitySummary.as_view(), name='quality-summary'),
    path('reports/publication/quality/<str:beamline>/', views.QualitySummary.as_view(), name='beamline-quality'),
    path('reports/publication/funding/', views.FundingSummary.as_view(), name='funding-summary'),
    path('reports/publication/institution/<int:pk>/', views.InstitutionMetrics.as_view(), name='institution-metrics'),

]