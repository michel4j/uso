from django.urls import path
from . import views, models
from misc.views import ManageAttachments

urlpatterns = [
    path('projects/', views.UserProjectList.as_view(), name="user-project-list"),
    path('projects/<int:pk>/', views.ProjectDetail.as_view(), name='project-detail'),
    path('projects/<int:pk>/team/', views.UpdateTeam.as_view(), name='edit-team'),
    path('projects/<int:pk>/refresh/', views.RefreshTeam.as_view(), name='refresh-team'),
    path('projects/<int:pk>/team/<int:user_pk>/remove/', views.TeamMemberDelete.as_view(), name="remove-team"),
    path('projects/<int:pk>/material/', views.UpdateMaterial.as_view(), name='edit-materials'),

    path('projects/<int:pk>/invoicing/', views.InvoicingList.as_view(), name="cycle-invoicing"),
    path('projects/<int:pk>/clarifications/new/', views.AskClarification.as_view(reference_model=models.Project), name='request-project-clarification'),
    path('projects/<int:pk>/clarifications/', views.ShowClarifications.as_view(), name='show-project-clarifications'),
    path('projects/<int:ref>/clarifications/<int:pk>/response/', views.AnswerClarification.as_view(), name='project-clarification-response'),
    path('projects/<int:pk>/attachments/manage/', ManageAttachments.as_view(reference_model=models.Project), name='project-attachments'),
    path('projects/<int:pk>/attachments/<slug:slug>/', ManageAttachments.as_view(reference_model=models.Project), name='get-project-attachment'),
    path('projects/<int:pk>/attachments/', views.ShowAttachments.as_view(), name='show-project-attachments'),
    path('projects/<int:pk>/history/', views.ProjectHistory.as_view(), name='project-history'),
    path('projects/<int:pk>/schedule/', views.ProjectSchedule.as_view(), name="project-schedule"),
    path('projects/<int:pk>/request/allocation/new/<str:fac>/<int:cycle>/', views.CreateAllocRequest.as_view(), name="create-alloc-request"),
    path('projects/<int:pk>/request/allocation/<int:fac>/edit/', views.CreateAllocRequest.as_view(), name="edit-alloc-request"),

    path('beamtime/', views.UserBeamTimeList.as_view(), name="user-beamtime-list"),

]