import threading

import requests
from django.conf import settings

ICON_MAP_DAY = {
    200: "wi-day-storm-showers", 201: "wi-day-storm-showers", 202: "wi-day-thunderstorm", 210: "wi-day-storm-showers", 211: "wi-day-lightning",
    212: "wi-day-lightning", 221: "wi-day-thunderstorm", 230: "wi-day-storm-showers", 231: "wi-day-storm-showers", 232: "wi-day-thunderstorm",
    300: "wi-day-sprinkle", 301: "wi-day-sprinkle", 302: "wi-day-sprinkle", 310: "wi-day-sprinkle", 311: "wi-day-sprinkle", 312: "wi-day-sprinkle",
    313: "wi-day-showers", 314: "wi-day-showers", 321: "wi-day-showers", 500: "wi-day-showers", 501: "wi-day-showers", 502: "wi-day-showers",
    503: "wi-day-showers", 504: "wi-day-showers", 511: "wi-day-rain-mix", 520: "wi-day-showers", 521: "wi-day-showers", 522: "wi-day-showers",
    531: "wi-day-showers", 600: "wi-day-snow", 601: "wi-day-snow", 602: "wi-day-snow", 611: "wi-day-rain-mix", 612: "wi-day-rain-mix",
    615: "wi-day-rain-mix", 616: "wi-day-rain-mix", 620: "wi-day-snow", 621: "wi-day-snow", 622: "wi-day-snow", 701: "wi-day-fog", 711: "wi-smoke",
    721: "wi-day-haze", 731: "wi-sandstorm", 741: "wi-day-fog", 751: "wi-sandstorm", 761: "wi-sandstorm", 762: "wi-volcano", 771: "wi-day-haze",
    781: "wi-tornado", 800: "wi-day-sunny", 801: "wi-day-cloudy", 802: "wi-day-cloudy", 803: "wi-day-cloudy", 804: "wi-day-cloudy", 900: "wi-tornado",
    901: "wi-tornado", 902: "wi-hurricane", 903: "wi-snowflake-cold", 904: "wi-hot", 905: "wi-strong-wind", 906: "wi-hail", 951: "wi-day-sunny",
    952: "wi-windy", 953: "wi-windy", 954: "wi-windy", 955: "wi-windy", 956: "wi-strong-wind", 957: "wi-strong-wind", 958: "wi-strong-wind",
    959: "wi-strong-wind", 960: "wi-storm-showers", 961: "wi-storm-showers", 962: "wi-hurricane",
}
ICON_MAP_NIGHT = {
    200: "wi-night-storm-showers", 201: "wi-night-storm-showers", 202: "wi-night-thunderstorm", 210: "wi-night-storm-showers",
    211: "wi-night-lightning", 212: "wi-night-lightning", 221: "wi-night-thunderstorm", 230: "wi-night-storm-showers", 231: "wi-night-storm-showers",
    232: "wi-night-thunderstorm", 300: "wi-night-sprinkle", 301: "wi-night-sprinkle", 302: "wi-night-sprinkle", 310: "wi-night-sprinkle",
    311: "wi-night-sprinkle", 312: "wi-night-sprinkle", 313: "wi-night-showers", 314: "wi-night-showers", 321: "wi-night-showers",
    500: "wi-night-showers", 501: "wi-night-showers", 502: "wi-night-showers", 503: "wi-night-showers", 504: "wi-night-showers",
    511: "wi-night-rain-mix", 520: "wi-night-showers", 521: "wi-night-showers", 522: "wi-night-showers", 531: "wi-night-showers",
    600: "wi-night-snow", 601: "wi-night-snow", 602: "wi-night-snow", 611: "wi-night-rain-mix", 612: "wi-night-rain-mix", 615: "wi-night-rain-mix",
    616: "wi-night-rain-mix", 620: "wi-night-snow", 621: "wi-night-snow", 622: "wi-night-snow", 701: "wi-night-fog", 711: "wi-smoke",
    721: "wi-night-haze", 731: "wi-sandstorm", 741: "wi-night-fog", 751: "wi-sandstorm", 761: "wi-sandstorm", 762: "wi-volcano", 771: "wi-night-haze",
    781: "wi-tornado", 800: "wi-night-clear", 801: "wi-night-cloudy", 802: "wi-night-cloudy", 803: "wi-night-cloudy", 804: "wi-night-cloudy",
    900: "wi-tornado", 901: "wi-tornado", 902: "wi-hurricane", 903: "wi-snowflake-cold", 904: "wi-hot", 905: "wi-strong-wind", 906: "wi-hail",
    951: "wi-night-clear", 952: "wi-windy", 953: "wi-windy", 954: "wi-windy", 955: "wi-windy", 956: "wi-strong-wind", 957: "wi-strong-wind",
    958: "wi-strong-wind", 959: "wi-strong-wind", 960: "wi-storm-showers", 961: "wi-storm-showers", 962: "wi-hurricane",
}

WEATHER_LOCATION = getattr(settings, 'USO_WEATHER_LOCATION', [52.14, -106.63])  # Default to CLSI
API_KEY = getattr(settings, 'USO_OPEN_WEATHER_KEY', '')


def get_conditions() -> dict:
    url = "https://api.openweathermap.org/data/2.5/weather"
    lat, lon = WEATHER_LOCATION
    params = {
        "appid": API_KEY,
        "lat": lat,
        "lon": lon,
        "units": "metric",
    }
    response = requests.get(url, params=params)
    if response.status_code == requests.codes.ok:
        info = response.json()
        conditions = {
            "lat": info.get("coord", {}).get("lat"),
            "lon": info.get("coord", {}).get("lon"),
            "current": {
                "dt": info.get("dt"),
                "temp": info.get("main", {}).get("temp"),
                "temp_min": info.get("main", {}).get("temp_min"),
                "temp_max": info.get("main", {}).get("temp_max"),
                "humidity": info.get("main", {}).get("humidity"),
                "feels_like": info.get("main", {}).get("feels_like"),
                "weather": info.get("weather", []),
                "sunrise": info.get("sys", {}).get("sunrise"),
                "sunset": info.get("sys", {}).get("sunset"),
            },
            'forecast': get_forecast(),
        }
        return conditions
    else:
        print(f"Error fetching weather data: {response.status_code} - {response.text}")
    return {}


def get_forecast() -> list[dict]:
    """
    Get the weather forecast for the next 5 days.
    """
    url = "https://api.openweathermap.org/data/2.5/forecast"
    lat, lon = WEATHER_LOCATION
    params = {
        "appid": API_KEY,
        "lat": lat,
        "lon": lon,
        "units": "metric",
    }
    response = requests.get(url, params=params)
    conditions = []
    if response.status_code == requests.codes.ok:
        forecasts = response.json()
        conditions = [
            {
                "dt": forecast.get("dt"),
                "temp": forecast.get("main", {}).get("temp"),
                "temp_min": forecast.get("main", {}).get("temp_min"),
                "temp_max": forecast.get("main", {}).get("temp_max"),
                "humidity": forecast.get("main", {}).get("humidity"),
                "feels_like": forecast.get("main", {}).get("feels_like"),
                "weather": forecast.get("weather", []),
            }
            for forecast in forecasts.get("list", [])
        ]
    else:
        print(f"Error fetching weather forecast: {response.status_code} - {response.text}")
    return conditions


def get_location_info() -> dict:
    """
    Get the location information for the weather service.
    """
    url = "https://api.openweathermap.org/geo/1.0/reverse"
    lat, lon = WEATHER_LOCATION
    params = {
        "appid": API_KEY,
        "lat": lat,
        "lon": lon,
        "limit": 1,
    }
    response = requests.get(url, params=params)
    if response.status_code == requests.codes.ok:
        location_info = response.json()
        if location_info:
            return location_info[0]
    else:
        print(f"Error fetching location info: {response.status_code} - {response.text}")
    return {}


def run_async(f):
    """ Run the specified function asynchronously in a thread. 
    Return values will not be available
    """

    def _f(*args, **kwargs):
        threading.Thread(target=f, args=args, kwargs=kwargs).start()

    _f.__name__ = f.__name__
    return _f
