import copy
import functools
import operator
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from misc.blocktypes import BaseBlock, BLOCK_TYPES


class ProposalsBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "proposals/blocks/proposals.html"
    priority = 1

    def check_allowed(self, request):
        return request.user.is_authenticated

    def render(self, context):
        ctx = copy.copy(context)
        from proposals import models
        user = context['request'].user

        filters = Q(leader_username=user.username) | Q(spokesperson=user) | Q(delegate_username=user.username)
        proposals = models.Proposal.objects.filter(filters)
        drafts = proposals.filter(state=models.Proposal.STATES.draft)

        submitted = proposals.filter(
            Q(state__gte=models.Proposal.STATES.submitted) &
            Q(submissions__state__lt=models.Submission.STATES.reviewed),
        ).distinct()
        open_cycles = models.ReviewCycle.objects.filter(state=models.Cycle.STATES.open)
        ctx.update({
            "drafts": drafts,
            "submitted": submitted,
            "open_cycles": open_cycles
        })
        return super().render(ctx)


class ReviewsBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "proposals/blocks/reviews.html"
    priority = 1

    def check_allowed(self, request):
        return request.user.is_authenticated

    def render(self, context):
        ctx = copy.copy(context)
        from proposals import models

        user = context['request'].user
        next_cycle = models.ReviewCycle.objects.next()

        filters = Q(reviewer=user)
        if user.roles:
            filters |= functools.reduce(operator.__or__, [Q(reviewer__isnull=True, role=r) for r in user.roles], Q())

        reviews = models.Review.objects.filter(filters).filter(
            state__gt=models.Review.STATES.pending, state__lt=models.Review.STATES.submitted,
        )
        show = reviews.exists()
        if hasattr(user, 'reviewer'):
            show = True
            reviewer = user.reviewer
            ctx.update({
                'reviewer': reviewer,
            })
            if next_cycle.state == next_cycle.STATES.review and reviewer.committee:
                ctx.update({
                    'committee_proposals': reviewer.committee_proposals(next_cycle).count()
                })

        soon = (timezone.now() + timedelta(weeks=12)).date()
        ctx.update({
            "reviews": reviews.filter(Q(due_date__lte=soon) | Q(due_date__isnull=True)).order_by('cycle', 'due_date'),
            "all_reviews": reviews,
            "next_cycle": next_cycle,
        })

        next_call = models.ReviewCycle.objects.next_call()
        if next_call:
            reviewer_available_next_call = models.Reviewer.objects.available(next_call).filter(user=user).exists()
            can_review = user.can_review()
            show |= can_review
            ctx.update({
                "upcoming_call": (
                    reviewer_available_next_call
                ),
                "next_call": next_call,
                "can_review": can_review,
            })
        if show:
            return super().render(ctx)


