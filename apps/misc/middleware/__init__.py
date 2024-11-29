import re

import ipaddress
from django.conf import settings
from django.http import Http404

INTERNAL_URLS = getattr(settings, 'INTERNAL_URLS', [])
CLIENT_ADDRESS_INDEX = getattr(settings, 'INTERNAL_PROXIES', 1)
INTERNAL_IPS = settings.INTERNAL_IPS


class IPAddressList(list):

    def __init__(self, *ips):
        super().__init__()
        self.extend([ipaddress.ip_network('{0}'.format(ip), strict=False) for ip in ips])

    def __contains__(self, address):
        ip = ipaddress.ip_address('{0}'.format(address))
        return any(ip in net for net in self)


if not isinstance(INTERNAL_IPS, IPAddressList):
    INTERNAL_IPS = IPAddressList(*INTERNAL_IPS)
    settings.INTERNAL_IPS = INTERNAL_IPS


def get_client_address(request):
    x_forwarded_for = [v for v in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if v.strip()]
    if len(x_forwarded_for) >= CLIENT_ADDRESS_INDEX > 0:
        ip = x_forwarded_for[-CLIENT_ADDRESS_INDEX]
    else:
        ip = request.META.get('REMOTE_ADDR')
    if re.match(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$', ip):
        return ip
    else:
        return '254.254.254.254'


class InternalAccessMiddleware(object):
    """
    Middleware to prevent access to the admin if the user IP
    isn't in the INTERNAL_IPS setting.
    """

    def _check_internal(self, request):
        self.internal_request = get_client_address(request) in INTERNAL_IPS
        if any(re.match(addr, request.path) for addr in INTERNAL_URLS) and not self.internal_request:
            return False
        else:
            return True

    def process_request(self, request):
        if not self._check_internal(request):
            raise Http404()

    def process_template_response(self, request, response):
        if self.internal_request and response.context_data:
            response.context_data['internal_request'] = self.internal_request
        return response
