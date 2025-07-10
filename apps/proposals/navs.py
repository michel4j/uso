from django.urls import reverse
from django.conf import settings
from misc.navigation import BaseNav

USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ['admin:uso'])
USO_STAFF_ROLES = getattr(settings, "USO_STAFF_ROLES", ['staff', 'employee'])
USO_HSE_ROLES = getattr(settings, "USO_HSE_ROLES", ['staff:hse', 'employee:hse'])


class Proposals(BaseNav):
    label = 'Proposals'
    icon = 'bi-file-earmark-medical'
    weight = 2.5
    roles = USO_ADMIN_ROLES
    url = reverse('proposal-list')

    def allowed(self, request):
        allowed = super().allowed(request)
        if not allowed and hasattr(request.user, "reviewer"):
            allowed = request.user.reviewer.committee is not None
        return allowed


class CurrentCycle(BaseNav):
    parent = Proposals
    label = 'Current Cycle'
    roles = USO_ADMIN_ROLES

    def get_url(self):
        from proposals.models import ReviewCycle
        cycle = ReviewCycle.objects.current().first()
        if not cycle:
            cycle = ReviewCycle.objects.next()

        return "" if not cycle else reverse('review-cycle-detail', kwargs={'pk': cycle.pk})


class NextCycle(BaseNav):
    parent = Proposals
    label = 'Next Cycle'
    roles = USO_ADMIN_ROLES

    def get_url(self):
        from proposals.models import ReviewCycle
        cycle = ReviewCycle.objects.next()
        return "" if not cycle else reverse('review-cycle-detail', kwargs={'pk': cycle.pk})


class Cycle(BaseNav):
    parent = Proposals
    label = 'All Cycles'
    roles = USO_ADMIN_ROLES
    url = reverse('review-cycle-list')


class InProgress(BaseNav):
    parent = Proposals
    label = 'Proposals In-Progress'
    roles = USO_ADMIN_ROLES
    url = reverse('proposals-inprogress')


class Submissions(BaseNav):
    parent = Proposals
    label = 'Proposal Submissions'
    roles = USO_ADMIN_ROLES
    url = reverse('submission-list')


class Reviewers(BaseNav):
    parent = Proposals
    label = 'Reviewer Profiles'
    roles = USO_ADMIN_ROLES
    url = reverse('reviewer-list')


class Reviews(BaseNav):
    parent = Proposals
    label = 'Reviews'
    roles = USO_ADMIN_ROLES
    url = reverse('review-list')


class Statistics(BaseNav):
    parent = Proposals
    label = 'Statistics'
    roles = USO_ADMIN_ROLES
    separator = True
    url = reverse('proposal-stats')


class UserProposals(BaseNav):
    label = 'My Proposals'
    parent = 'users.Home'
    url = reverse('user-proposals')


class PRCAssignments(BaseNav):
    label = 'My PRC Assignments'
    parent = Proposals
    url = reverse('personal-prc-reviews')

    def allowed(self, request):
        allowed = super().allowed(request)
        if not allowed and hasattr(request.user, "reviewer"):
            allowed = request.user.reviewer.committee is not None
        return allowed


class AccessPools(BaseNav):
    parent = 'misc.Admin'
    label = 'Access Pools'
    roles = USO_ADMIN_ROLES
    url = reverse('access-pool-list')
    separator = True
    weight = 100


class ReviewTracks(BaseNav):
    parent = 'misc.Admin'
    label = 'Review Tracks'
    roles = USO_ADMIN_ROLES
    url = reverse('review-track-list')
    weight = 101


class ReviewTypes(BaseNav):
    parent = 'misc.Admin'
    label = 'Review Types'
    roles = USO_ADMIN_ROLES
    url = reverse('review-type-list')
    weight = 105


class Techniques(BaseNav):
    parent = 'misc.Admin'
    label = 'Techniques'
    roles = USO_ADMIN_ROLES
    url = reverse('technique-list')
    weight = 110
