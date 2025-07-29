from django.urls import path

from agreements import views

urlpatterns = [
    path('agreements/', views.AgreementList.as_view(), name='agreement-list'),
    path('agreements/new/', views.CreateAgreement.as_view(), name='add-agreement'),
    path('agreements/<int:pk>/edit/', views.EditAgreement.as_view(), name='edit-agreement'),
    path('agreements/<slug:code>/accept/', views.AcceptAgreement.as_view(), name='accept-agreement'),
]
