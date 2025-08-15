from datetime import timedelta

from django.db.models import Q
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.utils.safestring import mark_safe

from misc.navigation import BaseNav, RawNav

USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ['admin:uso'])
USO_STAFF_ROLES = getattr(settings, "USO_STAFF_ROLES", ['staff'])
USO_HSE_ROLES = getattr(settings, "USO_HSE_ROLES", ['staff:hse'])


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

    def sub_menu(self, request):
        from .models import ReviewCycle
        now = timezone.localtime(timezone.now())
        in_six_months = now + timedelta(weeks=24)

        cycles = ReviewCycle.objects.filter(
            Q(open_date__lte=in_six_months.date()) & Q(end_date__gte=now.date())
        ).order_by('open_date')
        submenu = super().sub_menu(request)
        dynamic = [
            RawNav(
                label=mark_safe(f'Cycle &mdash; {cycle}'),
                roles=self.roles,
                separator=False,
                url=reverse('review-cycle-detail', kwargs={'pk': cycle.pk}),
            ) for cycle in cycles
        ]
        dynamic += [
            RawNav(
                label='All Cycles',
                roles=self.roles,
                separator=False,
                url=reverse('review-cycle-list'),
            )
        ]

        submenu[0].separator = True
        return dynamic + submenu


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


class CycleTypes(BaseNav):
    parent = 'misc.Admin'
    label = 'Cycle Types'
    roles = USO_ADMIN_ROLES
    url = reverse('cycle-type-list')
    separator = True
    weight = 95


class AccessPools(BaseNav):
    parent = 'misc.Admin'
    label = 'Access Pools'
    roles = USO_ADMIN_ROLES
    url = reverse('access-pool-list')
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
