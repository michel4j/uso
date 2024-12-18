from django.conf import settings
from misc.navigation import BaseNav
from django.urls import reverse


USO_STAFF_ROLES = getattr(settings, 'USO_STAFF_ROLES', ['staff'])
USO_CURATOR_ROLES = getattr(settings, 'USO_CURATOR_ROLES', ['curator:publications'])
USO_ADMIN_ROLES = getattr(settings, 'USO_ADMIN_ROLES', ['admin:uso'])


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
    roles = USO_STAFF_ROLES
    url = reverse('activity-summary')


class Metrics(BaseNav):
    parent = Publications
    label = 'Quality Metrics'
    roles = USO_STAFF_ROLES
    url = reverse('quality-summary')


class Funding(BaseNav):
    parent = Publications
    label = 'Funding Summary'
    roles = USO_STAFF_ROLES
    url = reverse('funding-summary')


class Manage(BaseNav):
    parent = Publications
    label = 'Edit Publications'
    roles = USO_CURATOR_ROLES + USO_ADMIN_ROLES
    url = reverse('publication-admin-list')


class Review(BaseNav):
    parent = Publications
    label = 'Review Submissions'
    roles = USO_CURATOR_ROLES + USO_ADMIN_ROLES
    url = reverse('publication-review-list')


class UserPublications(BaseNav):
    label = 'My Publications'
    parent = 'users.Home'
    url = reverse('user-publication-list')


class Matches(BaseNav):
    parent = 'users.Home'
    label = 'Manage My Publications'
    url = reverse('claim-publication-list')
