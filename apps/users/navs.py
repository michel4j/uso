from django.urls import reverse

from misc.navigation import BaseNav


class Home(BaseNav):
    label = 'Home'
    icon = 'bi-house'
    weight = 0
    url = reverse('user-dashboard')


class People(BaseNav):
    label = 'People'
    icon = 'bi-people'
    weight = 3
    roles = ['administrator:uso', 'contracts-administrator']
    url = reverse('users-list')


class Users(BaseNav):
    parent = People
    label = 'User Profiles'
    roles = ['administrator:uso']
    url = reverse('users-list')


class Reviewers(BaseNav):
    parent = People
    label = 'Reviewer Profiles'
    roles = ['administrator:uso']
    url = reverse('reviewer-list')


class Institutions(BaseNav):
    parent = People
    label = 'Institutions'
    roles = ['administrator:uso', 'contracts-administrator']
    url = reverse('institution-list')


class Dashboard(BaseNav):
    label = 'Dashboard'
    parent = Home
    url = reverse('user-dashboard')


class Profile(BaseNav):
    label = 'Edit Profile'
    parent = Home
    styles = "visible-xs"
    url = reverse('edit-my-profile')
    separator = True
    weight = 90


class Password(BaseNav):
    label = 'Change Password'
    parent = Home
    styles = "visible-xs"
    url = reverse('change-password')
    weight = 95


class Logout(BaseNav):
    label = 'Log Out'
    parent = Home
    weight = 100
    styles = "visible-xs"
    url = reverse('portal-logout')


class Agreements(BaseNav):
    parent = People
    label = 'Agreements'
    roles = ['administrator:uso', 'contracts-administrator']
    url = reverse('agreement-list')
