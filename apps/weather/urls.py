from django.urls import path
from django.views.decorators.cache import never_cache

from . import views

urlpatterns = [
    path('weather/', never_cache(views.WeatherDetailView.as_view()), name="weather-detail"),
]
