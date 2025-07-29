from django.urls import path

from samples import views

urlpatterns = [
    path('samples/', views.SampleListView.as_view(), name='sample-list'),
    path('samples/search/<int:pk>/', views.HSDBRecord.as_view(), name='compound-record'),
    path('samples/search/', views.HSDBSearch.as_view(), name='compound-search'),
    path('samples/help/', views.SampleHelp.as_view(), name='sample-help'),
    path('samples/field/', views.SampleField.as_view(), name='sample-field-root'),
    path('samples/field/<int:pk>/<str:field_name>/', views.SampleField.as_view(), name='sample-field'),
    path('samples/hazards/<int:pk>/<str:field_name>/', views.SampleHazards.as_view(), name='sample-hazards'),
    path('samples/permissions/<int:pk>/<str:field_name>/', views.SamplePermissions.as_view(), name='sample-permissions'),

    path('safety/permissions/', views.SafetyPermissionList.as_view(), name='safety-permission-list'),
    path('safety/permissions/<int:pk>/edit/', views.EditSafetyPermission.as_view(), name='edit-safety-permission'),
    path('safety/permissions/new/', views.AddSafetyPermission.as_view(), name='add-safety-permission'),
    path('safety/permissions/<int:pk>/delete/', views.DeleteSafetyPermission.as_view(), name='delete-safety-permission'),

    path('safety/substances/', views.HazardousSubstanceList.as_view(), name='hazardous-substance-list'),
    path('safety/substances/<int:pk>/edit/', views.EditHazardousSubstance.as_view(), name='edit-hazardous-substance'),
    path('safety/substances/new/', views.AddHazardousSubstance.as_view(), name='add-hazardous-substance'),
    path('safety/substances/<int:pk>/delete/', views.DeleteHazardousSubstance.as_view(), name='delete-hazardous-substance'),

]
