from django.urls import path

from samples import views

urlpatterns = [
    path('samples/', views.SampleListView.as_view(), name='sample-list'),
    path('samples/search/<int:pk>/', views.HSDBRecord.as_view(), name='compound-record'),
    path('samples/search/', views.HSDBSearch.as_view(), name='compound-search'),
    path('samples/help/', views.SampleHelp.as_view(), name='sample-help'),
    path('samples/field/', views.SampleField.as_view(), name='sample-field'),
    path('samples/field/<int:pk>/', views.SampleField.as_view(), name='sample-field'),
    path('samples/field/<int:pk>/<str:field_name>/', views.SampleField.as_view(), name='sample-field'),
    path('samples/hazards/<int:pk>/<str:field_name>/', views.SampleHazards.as_view(), name='sample-hazards'),
    path('samples/permissions/<int:pk>/<str:field_name>/', views.SamplePermissions.as_view(), name='sample-permissions'),
]
