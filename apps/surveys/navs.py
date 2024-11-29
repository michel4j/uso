from django.urls import reverse

from misc.navigation import BaseNav


class UserFeedback(BaseNav):
    label = 'Feedback'
    parent = 'users.Home'
    url = reverse('user-feedback')
