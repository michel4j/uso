from django.urls import reverse

from misc.navigation import BaseNav


class Proposals(BaseNav):
    label = 'Proposals'
    icon = 'bi-file-earmark-medical'
    weight = 2.5
    roles = ['administrator:uso']
    url = reverse('proposal-list')

    def allowed(self, request):
        allowed = super().allowed(request)
        if not allowed and hasattr(request.user, "reviewer"):
            allowed = request.user.reviewer.committee is not None
        return allowed


class CurrentCycle(BaseNav):
    parent = Proposals
    label = 'Current Cycle'
    roles = ['administrator:uso']

    def get_url(self):
        from proposals.models import ReviewCycle
        cycle = ReviewCycle.objects.current().first()
        return "" if not cycle else reverse('review-cycle-detail', kwargs={'pk': cycle.pk})


class NextCycle(BaseNav):
    parent = Proposals
    label = 'Next Cycle'
    roles = ['administrator:uso']

    def get_url(self):
        from proposals.models import ReviewCycle
        cycle = ReviewCycle.objects.next()
        return "" if not cycle else reverse('review-cycle-detail', kwargs={'pk': cycle.pk})


class Cycle(BaseNav):
    parent = Proposals
    label = 'All Cycles'
    roles = ['administrator:uso']
    url = reverse('review-cycle-list')


class InProgress(BaseNav):
    parent = Proposals
    label = 'Proposals In-Progress'
    roles = ['administrator:uso']
    url = reverse('proposals-inprogress')


class Submissions(BaseNav):
    parent = Proposals
    label = 'Proposal Submissions'
    roles = ['administrator:uso']
    url = reverse('submission-list')


class Reviewers(BaseNav):
    parent = Proposals
    label = 'Reviewer Profiles'
    roles = ['administrator:uso']
    url = reverse('reviewer-list')


class Reviews(BaseNav):
    parent = Proposals
    label = 'Reviews'
    roles = ['administrator:uso']
    url = reverse('review-list')


class Statistics(BaseNav):
    parent = Proposals
    label = 'Statistics'
    roles = ['administrator:uso']
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
