from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from django.views.decorators.cache import cache_page
from users.forms import LoginForm
from . import views

urlpatterns = [
    path('login/', LoginView.as_view(template_name='users/forms/login-form.html', form_class=LoginForm), name='portal-login'),
    path('logout/', LogoutView.as_view(), name='portal-logout'),
    path('registration/', views.RegistrationView.as_view(), name='portal-register'),
    path('registration/<str:hash>/', views.VerifyView.as_view(), name='portal-verify'),
    path('reset/', views.ResetPassword.as_view(), name="request-reset"),
    path('reset/<int:pk>/', views.AdminResetPassword.as_view(), name="admin-request-reset"),
    path('password/', views.ChangePassword.as_view(), name="change-password"),
    path('reset/<str:hash>/', views.PasswordView.as_view(), name='password-reset'),

    path('users/', views.UserList.as_view(), name="users-list"),
    path('users/<int:pk>/', views.UsersAdmin.as_view(), name="users-admin"),
    path('users/<str:username>/edit/', views.UpdateUserProfile.as_view(), name="edit-user-profile"),

    # Help
    #path('help/', generic.TemplateView.as_view(template_name='docs/doc_full.html'), name="help-page"),
    #path('info/', generic.TemplateView.as_view(template_name='docs/include_doc.html'), name="help-info"),
    #path('test-email/', views.EmailTestView.as_view(), name="email-test"),

    path('institutions/', views.InstitutionList.as_view(), name="institution-list"),
    path('institutions/new/', views.InstitutionCreate.as_view(), name="add-institution"),
    path('institutions/<int:pk>/edit/', views.EditInstitution.as_view(), name="edit-institution"),
    path('institutions/<int:pk>/delete/', views.InstitutionDelete.as_view(), name="delete-institution"),
    path('institutions/<int:pk>/contact/', views.InstitutionContact.as_view(), name="request-institution-contact"),

    path('photo/<str:path>', views.PhotoView.as_view(), name="user-photo"),
]