from django.urls import path

from beamlines import views

urlpatterns = [
    path('facilities/', views.BeamlineList.as_view(), name='beamline-list'),
    path('facilities/map/', views.BeamlineList.as_view(template_name="beamlines/selector.html"), name='beamline-map'),
    path('facilities/new/', views.CreateFacility.as_view(), name='create-beamline'),

    path('facilities/<slug:acronym>/', views.BeamlineDetail.as_view(), name='facility-detail'),
    path('facilities/<slug:acronym>/edit/', views.EditFacility.as_view(), name='edit-facility'),
    path('facilities/<int:fac>/support/<int:pk>/', views.ScheduleSupport.as_view(), name="schedule-support"),
    path(
        'facilities/<slug:acronym>/config/',
        views.BeamlineDetail.as_view(template_name="proposals/facility-config.html"),
        name='facility-config-detail'
    ),
    path('labs/', views.LaboratoryList.as_view(), name='lab-list'),
    path('labs/new/', views.CreateLaboratory.as_view(), name='create-lab'),
    path('labs/<slug:acronym>/', views.LaboratoryDetail.as_view(), name='lab-detail'),
    path('labs/<slug:acronym>/edit/', views.EditLaboratory.as_view(), name='edit-lab'),
    path('labs/<slug:acronym>/delete/', views.DeleteLaboratory.as_view(), name='delete-lab'),
    path('labs/<slug:acronym>/history/', views.LaboratoryHistory.as_view(), name='lab-history'),

    path('labs/<slug:acronym>/add', views.CreateWorkspace.as_view(), name='add-workspace'),
    path('workspace/<int:pk>/edit', views.EditWorkspace.as_view(), name='edit-workspace'),
    path('workspace/<int:pk>/delete', views.EditWorkspace.as_view(), name='delete-workspace'),
]
