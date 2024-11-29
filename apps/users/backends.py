import logging

from django.contrib.auth import get_user_model
from django_cas_ng.backends import CASBackend

User = get_user_model()
logger = logging.getLogger(__name__)

__all__ = ['PopulatedCASBackend']


class PopulatedCASBackend(CASBackend):
    def authenticate(self, ticket, service, request):
        """Verifies CAS ticket and gets or creates User object"""
        user = super().authenticate(ticket=ticket, service=service, request=request)
        if user:
            user.fetch_profile(force=True)
        return user

    # def get_user(self, user_id):
    #     """Retrieve the user's entry in the User model if it exists"""
    #
    #     try:
    #         return User.objects.get(pk=user_id)
    #     except User.DoesNotExist:
    #         return None

# @receiver(cas_user_authenticated)
# def handle_cas_login(sender, **kwargs):
#     print("USER AUTHENTICATED", kwargs)
