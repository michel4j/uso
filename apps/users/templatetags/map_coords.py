import json
import urllib.request, urllib.error, urllib.parse

from django import template

register = template.Library()


@register.filter(name='api_coords')
def api_coords(address):
    r = json.load(urllib.request.urlopen(
        f"https://maps.google.com/maps/api/geocode/json?address={address}&sensor=false"))
    if r['status'] == 'OK':
        try:
            return r['results'][0]['geometry']['location']
        except:
            pass
    return None
