from django.urls import reverse

from misc.navigation import BaseNav


class Samples(BaseNav):
    label = 'My Samples'
    parent = 'users.Home'
    url = reverse('user-sample-list')
