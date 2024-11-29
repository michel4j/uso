from django.urls import reverse

from misc.navigation import BaseNav


class Projects(BaseNav):
    label = 'Projects'
    icon = 'bi-briefcase'
    weight = 3
    roles = ['administrator:uso', 'safety-approver']
    url = reverse('project-list')


class Permits(BaseNav):
    label = 'Permits'
    icon = 'bi-key'
    weight = 2.5
    roles = ['employee']


class AllProjects(BaseNav):
    parent = Projects
    label = 'Projects'
    roles = ['administrator:uso', 'safety-approver']
    url = reverse('project-list')


class AllMaterials(BaseNav):
    parent = Projects
    label = 'Materials'
    roles = ['administrator:uso', 'safety-approver']
    url = reverse('material-list')


class AllSessions(BaseNav):
    parent = Permits
    label = 'Session Permits'
    roles = ['employee']
    url = reverse('session-list')


class LabPermits(BaseNav):
    label = 'Lab Permits'
    parent = Permits
    roles = ['employee']
    url = reverse('lab-permit-list')


class UserProjects(BaseNav):
    label = 'My Projects'
    parent = 'users.Home'
    url = reverse('user-project-list')


class UserBeamTime(BaseNav):
    label = 'My Beamtime'
    parent = 'users.Home'
    url = reverse('user-beamtime-list')


class Statistics(BaseNav):
    parent = Projects
    label = 'Statistics'
    roles = ['administrator:uso']
    separator = True
    url = reverse('project-stats')
