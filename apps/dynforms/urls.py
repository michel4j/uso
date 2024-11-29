from django.urls import path

from dynforms import views
###
# The field urls are used to manage the fields of a form from javascript. Since the javascript any changes to these
# urls will require changes to the javascript. The form urls are used to manage the form itself.
###
urlpatterns = [
    path('forms/', views.FormTypeList.as_view(), name='dynforms-list'),
    path('forms/<int:pk>/', views.EditFormView.as_view(), name='dynforms-builder'),
    path('forms/<int:pk>/run/', views.DynFormView.as_view(), name='dynforms-run'),

    # field urls
    path('forms/<int:pk>/<int:page>/add/<slug:type>/<int:pos>/', views.AddFieldView.as_view(), name='dynforms-add-field'),
    path('forms/<int:pk>/<int:page>/del/<int:pos>/', views.DeleteFieldView.as_view(), name='dynforms-del-field'),
    path('forms/<int:pk>/<int:page>/del/', views.DeletePageView.as_view(), name='dynforms-del-page'),
    path('forms/<int:pk>/<int:page>/put/<int:pos>/', views.EditFieldView.as_view(), name='dynforms-put-field'),
    path('forms/<int:pk>/<int:page>/get/<int:pos>/', views.GetFieldView.as_view(), name='dynforms-get-field'),
    path('forms/<int:pk>/<int:page>/mov/<int:from_pos>-<int:pos>/', views.MoveFieldView.as_view(), name='dynforms-move-field'),
    path('forms/<int:pk>/<int:page>/mov/<int:pos>/<int:to>/', views.PageFieldView.as_view(), name='dynforms-page-field'),
    path('forms/<int:pk>/<int:page>/rules/<int:pos>/', views.FieldRulesView.as_view(), name='dynforms-field-rules'),

    # form urls
    path('forms/<int:pk>/put/', views.EditFormView.as_view(), name='dynforms-edit-form'),
]