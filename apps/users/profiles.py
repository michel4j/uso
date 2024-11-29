import json

import requests
from django.conf import settings


class ExternalProfileManager:
    PROFILE_FIELDS = []

    @classmethod
    def fetch_profile(cls, username: str):
        """
        Called to fetch a user profile from the remote source. This is used to sync the specified user's
        profile from the remote source to the local database. Only fields specified in PROFILE_FIELDS will be changed in
        the User model.
        :param username: username of the user to fetch
        :return:
        """
        pass

    @classmethod
    def create_profile(cls, profile: dict):
        """
        Called to create a new profile in the remote source. User is expected to not exist in the remote source.
        :param profile: Dictionary of profile parameters.
        """
        pass

    @classmethod
    def update_profile(cls, username, profile: dict, photo=None):
        """
        Called to update the profile in the remote source. User is expected to exist in the remote source.

        :param profile: Dictionary of profile parameters.
        :param photo: File-like object of the user's photo
        """
        pass

    @classmethod
    def fetch_new_users(cls) -> list[dict]:
        """
        Fetch new users from the remote source. This is used to sync new users from the remote source to the local database.
        :return: list of dicts, one per user.
        """
        pass

    @classmethod
    def get_user_photo_url(cls, username: str):
        return f'{settings.MEDIA_URL}/idphoto/{username}.jpg'


class RemoteProfileManager(ExternalProfileManager):
    PROFILE_FIELDS = [
        'title', 'first_name', 'last_name', 'preferred_name', 'emergency_phone', 'other_names',
        'email', 'username', 'roles', 'permissions', 'emergency_contact',
    ]

    USER_PHOTO_URL = '{username}/photo'
    USER_PROFILE_URL = '{username}'
    USER_CREATE_URL = ''
    USER_LIST_URL = ''
    API_HEADERS = {'Content-Type': 'application/json'}

    SSL_VERIFY_CERTS = True

    @classmethod
    def fetch_profile(cls, username: str):
        url = cls.USER_PROFILE_URL.format(username=username)
        r = requests.get(url, headers=cls.API_HEADERS, verify=cls.SSL_VERIFY_CERTS)
        if r.status_code == requests.codes.ok:
            return r.json()
        else:
            return {}

    @classmethod
    def create_profile(cls, profile: dict):
        url = f'{settings.PEOPLE_DB_API}people/'
        r = requests.post(url, json=profile, headers=cls.API_HEADERS, verify=cls.SSL_VERIFY_CERTS)
        if r.status_code == requests.codes.ok:
            return r.json()
        else:
            return {}

    @classmethod
    def update_profile(cls, username: str, profile: dict, photo=None):
        url = cls.USER_PROFILE_URL.format(username=username)
        if photo:
            files = {'photo': (photo.name, photo, photo.content_type)}
            print(files)
            r = requests.patch(url, files=files, data=profile, headers=cls.API_HEADERS, verify=cls.SSL_VERIFY_CERTS)
        else:
            r = requests.patch(url, json=profile, headers=cls.API_HEADERS, verify=cls.SSL_VERIFY_CERTS)
        if r.status_code == requests.codes.ok:
            return r.json()
        else:
            return {}

    @classmethod
    def fetch_new_users(cls) -> list[dict]:
        r = requests.get(cls.USER_LIST_URL, headers=cls.API_HEADERS, verify=cls.SSL_VERIFY_CERTS)
        if r.status_code == requests.codes.ok:
            return r.json()['results']
        else:
            return []

    @classmethod
    def get_user_photo_url(cls, username: str):
        return cls.USER_PHOTO_URL.format(username=username)


