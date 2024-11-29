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

        cycle = models.ReviewCycle.objects.current().first()
        if not cycle:
            return ""
        filters = Q(leader_username=user.username) | Q(spokesperson=user) | Q(delegate_username=user.username)
        proposals = models.Proposal.objects.filter(filters)
        drafts = proposals.filter(state=models.Proposal.STATES.draft)
        submitted = proposals.filter(state=models.Proposal.STATES.submitted,
                                     submissions__cycle__start_date__gte=cycle.start_date).distinct()
        open_cycles = models.ReviewCycle.objects.filter(state=models.Cycle.STATES.open)
        ctx.update({
            "drafts": drafts,
            "submitted": submitted,
            "open_cycles": open_cycles
        })
        # if not (open_cycles.exists() or drafts.exists() or submitted.exists()):
        #     return ""
        return super().render(ctx)


class ReviewsBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "proposals/blocks/reviews.html"
    priority = 2

    def check_allowed(self, request):
        return request.user.is_authenticated

    def render(self, context):
        ctx = copy.copy(context)
        from proposals import models

        user = context['request'].user

        cycle = models.ReviewCycle.objects.current().first()
        if not cycle:
            return ""
        next_cycle = models.ReviewCycle.objects.next()

        filters = Q(reviewer=user)
        if user.roles:
            filters |= functools.reduce(operator.__or__, [Q(reviewer__isnull=True, role=r) for r in user.roles], Q())

        reviews = models.Review.objects.filter(filters).filter(
            state__gt=models.Review.STATES.pending, state__lte=models.Review.STATES.submitted,
        )

        amonth = (timezone.now() + timedelta(weeks=4)).date()
        if hasattr(user, 'reviewer'):
            reviewer = user.reviewer
            if next_cycle.state == next_cycle.STATES.review and reviewer.committee:
                ctx.update({
                    'committee_proposals': reviewer.committee_proposals(next_cycle).count()
                })
        elif not reviews.count():
            return None

        ctx.update({
            "reviews": reviews.filter(due_date__lte=amonth).order_by('due_date', 'created'),
            "all_reviews": reviews,
            "cycle": cycle,
            "next_cycle": next_cycle,
        })

        if cycle.state == cycle.STATES.active and next_cycle:
            ctx.update({
                "upcoming_call": (next_cycle.reviewers.filter(user=user).exists() and
                                  next_cycle.state == cycle.STATES.pending
                                  and next_cycle.open_date <= amonth),
                "can_review": user.reviews.filter(kind='scientific').exists() and not next_cycle.reviewers.filter(
                    user=user).exists(),
            })
        return super().render(ctx)
