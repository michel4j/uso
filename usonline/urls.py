
from django.conf import settings
from django.urls import include, re_path, path
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import reverse_lazy
from django.views.generic import RedirectView, TemplateView
from django.conf.urls.static import static
from misc.utils import iterload

from schema_graph.views import Schema

admin.site.site_header = "User Services Online"

urlpatterns = [
    path('', RedirectView.as_view(url=reverse_lazy('user-dashboard'), permanent=False)),
    path('', include('users.urls')),

    path('', include('proposals.urls')),
    path('', include('agreements.urls')),
    path('', include('publications.urls')),
    path('', include('beamlines.urls')),
    path('', include('scheduler.urls')),
    path('', include('projects.urls')),
    path('', include('samples.urls')),
    path('forms/', include('dynforms.urls')),
    path('reports/', include('reportcraft.urls')),
    path('messages/', include('notifier.urls')),
    path('', include('weather.urls')),
    path('', include('surveys.urls')),
    path('', include('isocron.urls')),

    path('admin/logout/', LogoutView.as_view()),
    path('admin/', admin.site.urls),
    path('misc/', include('misc.urls')),
]

# API URLS
for api_url in iterload('api_urls'):
    urlpatterns += [path('api/v1/', include(api_url))]

# User URLs
for user_url in iterload('user_urls'):
    urlpatterns += [path('user/', include(user_url))]

# Add media URLS for development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += [
        path('500/', TemplateView.as_view(template_name='500.html'), name='error-500'),
        path('503/', TemplateView.as_view(template_name='503.html'), name='error-503'),
        path('404/', TemplateView.as_view(template_name='404.html'), name='error-404'),
        path('403/', TemplateView.as_view(template_name='403.html'), name='error-403'),
        #path('schema/', Schema.as_view(), name='database-schema'),
    ]
