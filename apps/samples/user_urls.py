from django.urls import path

from samples import views

urlpatterns = [
    path('samples/', views.UserSampleListView.as_view(), name='user-sample-list'),
    path('samples/new/', views.SampleCreate.as_view(), name='add-sample-modal'),
    path('samples/<int:pk>/edit/', views.EditSample.as_view(), name='sample-edit-modal'),
    path('samples/<int:pk>/delete/', views.SampleDelete.as_view(), name='sample-delete'),
]
