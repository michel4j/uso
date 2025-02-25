from django.urls import path

from beamlines import views

urlpatterns = [
    path('facilities/', views.BeamlineList.as_view(), name='beamline-list'),
    path('facilities/map/', views.BeamlineList.as_view(template_name="beamlines/selector.html"), name='beamline-map'),
    path('facilities/new/', views.CreateFacility.as_view(), name='create-beamline'),
    path('facilities/<int:pk>/', views.BeamlineDetail.as_view(), name='facility-detail'),
    path('facilities/<slug:fac>/', views.BeamlineDetail.as_view(), name='facility-detail'),
    path('facilities/<int:pk>/edit/', views.EditFacility.as_view(), name='edit-beamline'),
    path('facilities/<int:fac>/support/<int:pk>/', views.ScheduleSupport.as_view(), name="schedule-support"),
    path(
        'facilities/config/<int:pk>/',
        views.BeamlineDetail.as_view(template_name="proposals/facility-config.html"),
        name='facility-config-detail'
    ),
    path('facilities/port/<slug:port>/', views.PortDetails.as_view(), name='port-details'),

    path('labs/', views.LaboratoryList.as_view(), name='lab-list'),
    path('labs/<int:pk>/', views.LaboratoryDetail.as_view(), name='lab-detail'),
    path('labs/<int:pk>/history/', views.LaboratoryHistory.as_view(), name='lab-history'),
]
