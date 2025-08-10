from django.urls import path

from . import views

urlpatterns = [
    path('attachments/<slug:slug>/del', views.DeleteAttachment.as_view(), name='del-attachment'),
    path('ping/', views.Ping.as_view(), name='ping-server'),
    path('reports/<slug:section>/', views.SectionIndex.as_view(), name='report-section-index'),
    path('reports/<slug:section>/<slug:slug>/', views.SectionReport.as_view(), name='report-section-view'),
    path('reports/<slug:section>/<slug:slug>/print/', views.SectionReport.as_view(template_name="misc/report-print.html"), name='report-section-print'),
    path('reports/<slug:section>/<slug:slug>/data/', views.SectionData.as_view(), name='report-section-data'),
]
