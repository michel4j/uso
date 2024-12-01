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


def get_conditions(city="6141256"):
    url = "https://api.openweathermap.org/data/2.5/weather"
    url_forecast = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "APPID": settings.USO_OPEN_WEATHER_KEY, "id": city, "units": "metric"
    }
    rc = requests.get(url, params=params)
    rf = requests.get(url_forecast, params=params)
    if rc.status_code == requests.codes.ok and rf.status_code == requests.codes.ok:
        forecast = rf.json().get('list')
        if not forecast:
            return
        conditions = {
            'current': rc.json(), 'forecast': forecast,
        }
        c = conditions['current']
        c['main']['windchill'] = windchill(c['main']['temp'], c['wind']['speed'])
        for c in [_f for _f in conditions['forecast'] if _f]:
            c['main']['windchill'] = windchill(c['main']['temp'], 0 if not c['wind'] else c['wind']['speed'])
        return conditions


def windchill(t, v):
    v = v * 60 * 60 / 1000.0  # convert to km/h
    if t <= 0 and 0 > v < 5:
        return int(round(t + v * (-1.59 + 0.1345 * t) / 5, 0))
    else:
        return int(round(13.12 + 0.6215 * t - 11.37 * v ** 0.16 + 0.3965 * t * v ** 0.16, 0))


def run_async(f):
    """ Run the specified function asynchronously in a thread. 
    Return values will not be available
    """

    def _f(*args, **kwargs):
        threading.Thread(target=f, args=args, kwargs=kwargs).start()

    _f.__name__ = f.__name__
    return _f
