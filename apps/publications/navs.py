from misc.navigation import BaseNav
from django.urls import reverse
from datetime import datetime


class Publications(BaseNav):
    label = 'Publications'
    icon = 'bi-journals'
    weight = 2


class List(BaseNav):
    parent = Publications
    label = 'All Publications'
    url = reverse('publication-list')


class Keywords(BaseNav):
    parent = Publications
    label = 'Keyword Cloud'
    url = reverse('keyword-cloud')


class Summary(BaseNav):
    parent = Publications
    label = 'Facility Summary'
    permissions = ['employee']
    url = reverse('activity-summary')


class Metrics(BaseNav):
    parent = Publications
    label = 'Quality Metrics'
    permissions = ['employee']
    url = reverse('quality-summary')


class Funding(BaseNav):
    parent = Publications
    label = 'Funding Summary'
    permissions = ['employee']
    url = reverse('funding-summary')


class Manage(BaseNav):
    parent = Publications
    label = 'Edit Publications'
    roles = ['publications-admin']
    url = reverse('publication-admin-list')


class Review(BaseNav):
    parent = Publications
    label = 'Review Submissions'
    roles = ['publications-admin']
    url = reverse('publication-review-list')


class UserPublications(BaseNav):
    label = 'My Publications'
    parent = 'users.Home'
    url = reverse('user-publication-list')


class Matches(BaseNav):
    parent = 'users.Home'
    label = 'Manage My Publications'
    url = reverse('claim-publication-list')
