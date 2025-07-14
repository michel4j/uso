from collections import defaultdict
from datetime import timedelta
from typing import Sequence

from crisp_modals.views import ModalCreateView, ModalUpdateView, ModalDeleteView, ModalConfirmView
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q, Avg, StdDev, Count, F
from django.http import HttpResponseRedirect, JsonResponse, Http404
from django.template.defaultfilters import pluralize
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.generic import detail, edit, TemplateView, View
from dynforms.models import FormType
from dynforms.views import DynUpdateView, DynCreateView
from itemlist.views import ItemListView

from scipy.stats import percentileofscore

from beamlines.models import Facility
from misc import filters
from misc.models import ActivityLog
from misc.utils import debug_value
from misc.views import ClarificationResponse, RequestClarification
from notifier import notify
from roleperms.views import RolePermsViewMixin
from users.models import User
from . import forms
from . import models
from . import utils
from .filters import CycleFilterFactory
from .models import ReviewType
from .templatetags import proposal_tags

USO_SAFETY_REVIEWS = getattr(settings, 'USO_SAFETY_REVIEWS', [])
USO_SCIENCE_REVIEWS = getattr(settings, 'USO_SCIENCE_REVIEWS', [])
USO_SAFETY_APPROVAL = getattr(settings, 'USO_SAFETY_APPROVAL', "approval")
USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ['admin:uso'])
USO_STAFF_ROLES = getattr(settings, "USO_STAFF_ROLES", ['staff', 'employee'])
USO_HSE_ROLES = getattr(settings, "USO_HSE_ROLES", ['staff:hse', 'employee:hse'])
USO_MANAGER_ROLES = getattr(settings, "USO_MANAGER_ROLES", ['manager:science'])


def _state_lbl(st, obj=None):
    return '<i class="icon-sm {0} {1} text-center" title="{2}"></>'.format(
        proposal_tags.state_icon(st), st, models.Proposal.STATES[st]
    )


def _fmt_beamlines(bls, obj=None):
    return ', '.join([bl.acronym for bl in bls.all()])


def _fmt_review_state(state, obj=None):
    return proposal_tags.display_state(obj)


def _fmt_role(role, obj=None):
    if not role:
        return "&hellip;"
    name, realm = (role, '') if ':' not in role else role.split(':')
    if realm:
        return f"{name.replace('-', ' ').title()} ({realm.upper()})"
    else:
        return name.replace('-', ' ').title()


class UserProposalList(RolePermsViewMixin, ItemListView):
    template_name = "proposals/proposal-list.html"
    list_columns = ['title', 'state', 'created']
    list_filters = ['state', 'modified', 'created']
    list_transforms = {'state': _state_lbl, }
    link_url = "proposal-detail"
    add_url = "create-proposal"
    list_search = ['title', 'areas__name', 'keywords']
    order_by = ['state', '-modified']
    list_title = 'My Proposals'
    paginate_by = 25

    def get_queryset(self, *args, **kwargs):
        flts = (
            Q(spokesperson=self.request.user) |
            Q(leader_username=self.request.user.username) |
            Q(delegate_username=self.request.user.username) 
        )

        if self.request.user.email:
            flts |= Q(team__icontains=self.request.user.email)
        if self.request.user.alt_email:
            flts |= Q(team__icontains=self.request.user.alt_email)

        self.queryset = models.Proposal.objects.filter(flts)
        return super().get_queryset(*args, **kwargs)


class ProposalList(RolePermsViewMixin, ItemListView):
    template_name = "item-list.html"
    list_title = 'All Draft Proposals'
    allowed_roles = USO_ADMIN_ROLES
    list_columns = ['title', 'spokesperson', 'id', 'state']
    list_filters = ['state', 'modified', 'created']
    list_transforms = {'state': _state_lbl, }
    link_url = "proposal-detail"
    add_url = "create-proposal"
    list_search = ['title', 'areas__name', 'keywords']
    order_by = ['state', 'created']
    paginate_by = 15

    def get_queryset(self, *args, **kwargs):
        self.queryset = models.Proposal.objects.filter(state=models.Proposal.STATES.draft)
        return super().get_queryset(*args, **kwargs)


class FacilityDraftProposals(ProposalList):
    list_title = 'Facility Draft Proposals'

    def check_allowed(self):
        allowed = super().check_allowed()
        facility = Facility.objects.filter(acronym__iexact=self.kwargs['slug']).first()
        if not facility:
            return False
        allowed |= facility.is_admin(self.request.user)
        return allowed

    def get_queryset(self, *args, **kwargs):
        queryset = super().get_queryset(*args, **kwargs)
        facility = Facility.objects.filter(acronym__iexact=self.kwargs['slug']).first()
        self.queryset = queryset.filter(state=models.Proposal.STATES.draft).filter(
            details__beamline_reqs__contains=[{'facility': facility.pk}]
        )
        return self.queryset


class PRCList(RolePermsViewMixin, ItemListView):
    template_name = "item-list.html"
    allowed_roles = USO_ADMIN_ROLES
    list_columns = ['user', 'committee', 'active']
    list_filters = ['modified', 'created']
    link_url = "prc-reviews"
    add_url = "create-proposal"
    list_search = ['title', 'areas__name', 'keywords']
    order_by = ['user__last_name', 'created']

    def get_list_title(self):
        return f'Peer-Reviewers - {self.track} Track'

    def get_detail_url(self, obj):
        return reverse('prc-reviews', kwargs={'cycle': self.cycle.pk, 'pk': obj.pk})

    def get_queryset(self, *args, **kwargs):
        self.track = models.ReviewTrack.objects.get(acronym=self.kwargs['track'])
        self.cycle = models.ReviewCycle.objects.get(pk=self.kwargs['cycle'])
        self.queryset = models.Reviewer.objects.filter(committee=self.track)
        return super().get_queryset(*args, **kwargs)


class CreateProposal(RolePermsViewMixin, DynCreateView):
    template_name = 'proposals/proposal-form.html'
    model = models.Proposal
    form_class = forms.ProposalForm

    def get_form_type(self) -> FormType:
        form_type = FormType.objects.filter(code='proposal').first()
        if not form_type:
            raise Http404("Proposal form type not found.")
        return form_type

    def get_success_url(self):
        if self._form_action == 'save_continue':
            success_url = reverse("edit-proposal", kwargs={'pk': self.object.pk})
        else:
            success_url = reverse("proposal-detail", kwargs={'pk': self.object.pk})
        return success_url

    def form_valid(self, form):
        data = form.cleaned_data
        data['spokesperson'] = self.request.user

        self.object = self.model.objects.create(**form.cleaned_data)
        msg = 'Draft proposal created'
        messages.success(self.request, msg)
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.create, description=msg
        )
        self._form_action = form.cleaned_data['details']['form_action']
        return HttpResponseRedirect(self.get_success_url())


class EditProposal(RolePermsViewMixin, DynUpdateView):
    template_name = 'proposals/proposal-form.html'
    model = models.Proposal
    form_class = forms.ProposalForm
    admin_roles = USO_ADMIN_ROLES

    def check_owner(self, obj):
        qchain = Q(leader_username=self.request.user.username) | Q(spokesperson=self.request.user) | Q(
            delegate_username=self.request.user.username
        )
        self.queryset = models.Proposal.objects.filter(state=models.Proposal.STATES.draft).filter(qchain)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = max(1, context['object'].details.get('active_page', 1))
        return context

    def get_success_url(self):
        if self._form_action == 'save_continue':
            success_url = reverse("edit-proposal", kwargs={'pk': self.object.pk})
        else:
            success_url = reverse("proposal-detail", kwargs={'pk': self.object.pk})
        return success_url

    def get_queryset(self, *args, **kwargs):
        if self.check_admin():
            self.queryset = models.Proposal.objects.filter(state=models.Proposal.STATES.draft)
        else:
            qchain = Q(leader_username=self.request.user.username) | Q(spokesperson=self.request.user) | Q(
                delegate_username=self.request.user.username
            )
            self.queryset = models.Proposal.objects.filter(state=models.Proposal.STATES.draft).filter(qchain)
        return super().get_queryset(*args, **kwargs)

    def form_valid(self, form):
        data = form.cleaned_data
        subject_areas = data.get('subject', {})
        areas = subject_areas.get('areas', [])
        keywords = subject_areas.get('keywords', '')
        self.object.keywords = keywords
        self.object.areas.add(*areas)
        self.object.save()
        self.queryset.filter(pk=self.object.pk).update(**data)
        messages.success(self.request, 'Draft proposal was saved successfully')
        self._form_action = form.cleaned_data['details']['form_action']
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.modify, description='Proposal edited'
        )
        return HttpResponseRedirect(self.get_success_url())


class CloneProposal(RolePermsViewMixin, ModalConfirmView):
    template_name = 'proposals/forms/clone.html'
    success_url = reverse_lazy('user-proposals')

    def get_queryset(self):
        qchain = Q(leader_username=self.request.user.username) | Q(spokesperson=self.request.user) | Q(
            delegate_username=self.request.user.username
        )
        self.queryset = models.Proposal.objects.filter(qchain)
        return super().get_queryset()

    def confirmed(self, *args, **kwargs):
        messages.add_message(self.request, messages.SUCCESS, 'Proposal has been cloned. [Copy] added to title.')
        self.object = super().get_object()
        self.object.pk = None
        self.object.state = self.object.STATES.draft
        self.object.title = f"[COPY] {self.object.title}"
        self.object.created = timezone.now()
        self.object.modified = timezone.now()
        self.object.details['active_page'] = 1
        self.object.save()
        success_url = reverse('edit-proposal', kwargs={'pk': self.object.pk})
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.task, description='Proposal cloned'
        )
        return JsonResponse(
            {
                "url": success_url
            }
        )


def expand_role(role: str, realms: list[str]) -> set[str]:
    """
    Expand a role string into a set of roles. substituting any wildcards with the full set of roles.
    :param role: The role to expand
    :param realms: List of realms to expand the role into
    :return: set of roles
    """

    return {
        role.format(realm) for realm in realms if role.strip()
    }


class SubmitProposal(RolePermsViewMixin, ModalUpdateView):
    model = models.Proposal
    form_class = forms.SubmitProposalForm
    #template_name = "proposals/forms/submit.html"
    success_url = reverse_lazy('user-proposals')
    submit_info: dict

    def get_queryset(self):
        query = (Q(leader_username=self.request.user.username) | Q(spokesperson=self.request.user) | Q(
            delegate_username=self.request.user.username
        ))
        self.queryset = models.Proposal.objects.filter(state=models.Proposal.STATES.draft).filter(query)
        return super().get_queryset()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.submit_info = self.prepare_submission()
        kwargs['submit_info'] = self.submit_info
        return kwargs

    def prepare_submission(self):
        """
        Determine the available review tracks and submission options for the current user and the proposal's
        instrument requirements.
        :return:
        """
        requirements = self.object.details['beamline_reqs']
        cycle = models.ReviewCycle.objects.get(pk=self.object.details['first_cycle'])
        techniques = models.ConfigItem.objects.none()
        facility_acronyms = set()
        for req in requirements:
            config = models.FacilityConfig.objects.for_facility(req.get('facility')).get_for_cycle(cycle)
            if config:
                acronym = config.facility.acronym.lower()
                facility_acronyms.add(acronym)
                techniques |= config.items.filter(technique__in=req.get('techniques', []))

        # Select available pools
        # A pool is available if it doesn't define any roles, or the user matches one of the defined roles
        pool_roles = {
            pool.pk: expand_role(pool.role, list(facility_acronyms))
            for pool in models.AccessPool.objects.all()
        }
        available_pool_ids = [
            pk for pk, roles in pool_roles.items() if self.request.user.has_any_role(*roles) or not roles
        ]

        # Select available tracks based on requested techniques and call status
        if cycle.is_closed():
            valid_tracks = models.ReviewTrack.objects.filter(require_call=False)
        else:
            valid_tracks = models.ReviewTrack.objects.filter(require_call=True)

        available_tracks = set(valid_tracks.values_list('pk', flat=True))
        requests = {
            track: track_techniques
            for track, track_techniques in techniques.group_by_track().items()
            if track_techniques.exists()
        }

        invalid_tracks = set()
        valid_tracks = set()
        valid_track_techniques = set()
        invalid_track_techniques = set()

        for track, techniques in requests.items():
            if track.pk in available_tracks:
                valid_tracks.add(track.pk)
                valid_track_techniques.update(techniques.values_list('technique__pk', flat=True))
            else:
                invalid_tracks.add(track.pk)
                invalid_track_techniques.update(techniques.values_list('technique__pk', flat=True))

        invalid_techniques = invalid_track_techniques - valid_track_techniques

        if not valid_tracks:
            message = (
                "No review tracks are available for submission. Select a different cycle or check back "
                "during the next call for proposals."
            )
        elif len(valid_tracks) > 1:
            message = (
                "Multiple review tracks are available. Please select at least one track to submit your proposal. "
                "You can select multiple tracks if your proposal is relevant to more than one track."
            )
        else:
            message = (
                "One review track is available for submission, therefore it has been pre-selected."
            )
        num_invalid = len(invalid_techniques)
        if num_invalid > 0:

            message += (
                f" <span class='text-danger'>{num_invalid} "
                f"technique{pluralize(num_invalid, ' is,s are')} not available for submission</span> "
            )

        info = {
            "message": mark_safe(message),
            "requests": requests,
            "valid_tracks": valid_tracks,
            "invalid_tracks": invalid_tracks,
            "invalid_techniques": invalid_techniques,
            "num_tracks": len(requests),
            "cycle": cycle,
            "pools": models.AccessPool.objects.filter(pk__in=available_pool_ids),
        }
        return info

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.submit_info)
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        access_pool = data['access_pool']
        tracks = data['tracks']
        cycle = self.submit_info["cycle"]
        track_ids = tracks.values_list('pk', flat=True)
        self.object = super().get_object()

        # create submissions
        for track, items in list(self.submit_info['requests'].items()):
            if track.pk not in track_ids:
                continue

            obj = models.Submission.objects.create(proposal=self.object, track=track, pool=access_pool, cycle=cycle)
            obj.techniques.add(*items)
            obj.save()

        # update state
        self.object.state = self.object.STATES.submitted
        self.object.save()

        # lock all attachments
        self.object.attachments.all().update(is_editable=False)

        # notify team members of a submitted proposal
        utils.notify_submission(self.object, cycle)
        messages.add_message(self.request, messages.SUCCESS, 'Proposal has been submitted.')
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.task, description='Proposal submitted'
        )

        return JsonResponse({
            "url": "."
        })


class ProposalDetail(RolePermsViewMixin, detail.DetailView):
    template_name = "proposals/proposal-detail.html"
    model = models.Proposal
    admin_roles = USO_ADMIN_ROLES
    allowed_roles = USO_ADMIN_ROLES + USO_STAFF_ROLES

    def check_owner(self, obj):
        return self.request.user.username in [obj.spokesperson.username, obj.delegate_username, obj.leader_username]

    def check_allowed(self):
        proposal = self.get_object()
        user = self.request.user
        emails = {e.strip().lower() for e in [user.email, user.alt_email] if e}
        return super().check_allowed() or self.check_owner(proposal) or (len(emails & set(proposal.team)) > 0)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['validation'] = self.object.validate()
        return context


class DeleteProposal(RolePermsViewMixin, ModalDeleteView):
    success_url = reverse_lazy('user-proposals')
    allowed_roles = USO_ADMIN_ROLES

    def check_owner(self, obj):
        return self.request.user.username in [obj.spokesperson.username, obj.delegate_username, obj.leader_username]

    def check_allowed(self):
        proposal = self.get_object()
        return super().check_allowed() or self.check_owner(proposal)

    def get_queryset(self):
        self.queryset = models.Proposal.objects.filter(
            Q(leader_username=self.request.user.username) | Q(spokesperson=self.request.user) | Q(
                delegate_username=self.request.user.username
            )
        )
        return super().get_queryset()


class EditReviewerProfile(RolePermsViewMixin, edit.FormView):
    form_class = forms.ReviewerForm
    template_name = "proposals/forms/form.html"
    model = models.Reviewer
    success_message = "Reviewer profile has been updated."
    admin_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        if self.check_admin():
            return reverse_lazy("reviewer-list")
        else:
            return reverse_lazy("user-dashboard")

    def get_initial(self, *args, **kwargs):
        initial = super().get_initial()
        if self.kwargs.get('pk'):
            reviewer = models.Reviewer.objects.filter(pk=self.kwargs.get('pk')).first()
        else:
            reviewer = models.Reviewer.objects.filter(user=self.request.user).first()

        if reviewer:
            initial['reviewer'] = reviewer
            initial['areas'] = reviewer.areas.all()
            initial['techniques'] = reviewer.techniques.all()
            initial['sub_areas'] = reviewer.areas.all()
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['admin'] = self.check_admin()
        return kwargs

    def form_valid(self, form):
        if self.kwargs.get('pk'):
            reviewer = models.Reviewer.objects.filter(pk=self.kwargs.get('pk')).first()
        else:
            reviewer, created = models.Reviewer.objects.get_or_create(user=self.request.user)

        if self.request.POST.get('submit') == 'disable':
            models.Reviewer.objects.filter(pk=reviewer.pk).update(active=False)
            messages.add_message(self.request, messages.SUCCESS, f'Reviewer {reviewer} Disabled')
        elif self.request.POST.get('submit') == 'enable':
            models.Reviewer.objects.filter(pk=reviewer.pk).update(active=True)
            messages.add_message(self.request, messages.SUCCESS, f'Reviewer {reviewer} Re-enabled')
        elif self.request.POST.get('submit') == 'suspend':
            models.Reviewer.objects.filter(pk=reviewer.pk).update(declined=timezone.now().date())
            messages.add_message(self.request, messages.SUCCESS, f'Reviewer {reviewer} Suspended')
        elif self.request.POST.get('submit') == 'reinstate':
            models.Reviewer.objects.filter(pk=reviewer.pk).update(declined=None)
            messages.add_message(self.request, messages.SUCCESS, f'Reviewer {reviewer} Reinstated')

        # add added entries
        reviewer.areas.add(*form.cleaned_data.get('areas', []))
        reviewer.techniques.add(*form.cleaned_data.get('techniques', []))

        # remove removed entries
        del_techs = set(reviewer.techniques.all()) - set(form.cleaned_data.get('techniques', []))
        del_areas = set(reviewer.areas.all()) - set(form.cleaned_data.get('areas', []))
        reviewer.techniques.remove(*del_techs)
        reviewer.areas.remove(*del_areas)
        ActivityLog.objects.log(
            self.request, reviewer, kind=ActivityLog.TYPES.modify, description='Reviewer profile edited'
        )
        return HttpResponseRedirect(self.get_success_url())


class ReviewList(RolePermsViewMixin, ItemListView):
    queryset = models.Review.objects.all()
    template_name = "item-list.html"
    paginate_by = 25
    list_columns = ['type', 'title', 'stage', 'role', 'reviewer', 'state', 'due_date']
    list_filters = ['created', 'modified', CycleFilterFactory.new('cycle'),
                    filters.FutureDateListFilterFactory.new('due_date'), 'state', 'type']

    list_search = ['reviewer__last_name', 'reviewer__first_name', 'role']
    link_url = "edit-review"
    ordering = ['state', 'due_date', '-created']
    list_transforms = {'state': _fmt_review_state, 'role': _fmt_role}
    admin_roles = USO_ADMIN_ROLES


class StageReviewList(ReviewList):
    list_title = 'Stage Reviews'
    template_name = "tooled-item-list.html"
    tool_template = "proposals/stage-review-tools.html"

    def get_list_title(self):
        stage = models.ReviewStage.objects.filter(pk=self.kwargs.get('stage')).first()
        cycle = models.ReviewCycle.objects.filter(pk=self.kwargs.get('cycle')).first()
        if stage and cycle:
            return f"{cycle} / {stage} - Reviews"
        else:
            return self.list_title

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cycle'] = models.ReviewCycle.objects.filter(pk=self.kwargs.get('cycle')).first()
        context['stage'] = models.ReviewStage.objects.filter(pk=self.kwargs.get('stage')).first()
        return context

    def get_queryset(self, *args, **kwargs):
        self.queryset = models.Review.objects.filter(
            cycle=self.kwargs.get('cycle'), stage=self.kwargs.get('stage'),
        )
        return super().get_queryset(*args, **kwargs)


class UserReviewList(ReviewList):
    list_title = 'My Reviews'

    def get_queryset(self, *args, **kwargs):
        self.queryset = models.Review.objects.filter(
            state__gt=models.Review.STATES.pending, state__lte=models.Review.STATES.submitted, ).filter(
            Q(reviewer=self.request.user) | Q(role__in=self.request.user.roles)
        )
        return super().get_queryset(*args, **kwargs)


class ClaimReview(RolePermsViewMixin, ModalConfirmView):
    model = models.Review
    template_name = "proposals/forms/claim.html"
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES
    success_url = "/"

    def check_allowed(self):
        allowed = super().check_allowed() or self.check_admin()
        if not allowed:
            obj = self.get_object()
            if not obj.role and obj.reviewer:
                return False
            allowed = self.request.user.has_role(obj.role)
        return allowed

    def get_object(self, **kwargs):
        obj = super().get_object()
        self.object = self.model.objects.filter(pk=obj.pk).first()
        return self.object

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.model.objects.filter(role__isnull=False)
        return super().get_queryset(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['candidates'] = User.objects.all_with_roles(context['review'].role)
        return context

    def confirmed(self, *args, **kwargs):
        obj = self.get_object()
        models.Review.objects.filter(pk=obj.pk).update(reviewer=self.request.user)
        ActivityLog.objects.log(
            self.request, obj, kind=ActivityLog.TYPES.task, description='Review Claimed'
        )
        return JsonResponse(
            {
                "url": ""
            }
        )


class PrintReviewDoc(RolePermsViewMixin, detail.DetailView):
    queryset = models.Review.objects.exclude(state=models.Review.STATES.closed)
    template_name = "proposals/pdf.html"
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        allowed = super().check_allowed()
        if not allowed:
            obj = self.get_object()
            allowed = (obj.reviewer == self.request.user or self.request.user.has_role(obj.role))
        return allowed

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reference'] = self.object.reference
        context['now'] = timezone.localtime(timezone.now())

        return context


def select_ethics_decision(items):
    if 'protocol' in items:
        return 'protocol'
    elif 'ethics' in items:
        return 'certificate'
    elif 'exempt' in items:
        return 'exempt'
    else:
        return None


class EditReview(RolePermsViewMixin, DynUpdateView):
    queryset = models.Review.objects.all()
    form_class = forms.ReviewForm
    template_name = "proposals/review-form.html"
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        allowed = super().check_allowed()
        if not allowed:
            obj = self.get_object()
            allowed = (
                obj.state != models.Review.STATES.closed and (
                obj.reviewer == self.request.user or self.request.user.has_role(obj.role))
            )
        return allowed

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if context['review'].is_claimable():
            context['candidates'] = User.objects.all_with_roles(context['review'].role)

            # if only one person, assign as the reviewer
            if len(context['candidates']) == 1 and not self.object.reviewer:
                context['review'].reviewer = context['candidates'][0]
                context['review'].save()
        else:
            context['candidates'] = []
        context['reference'] = self.object.reference
        return context

    def _valid_review(self, data, form_action):
        self.success_url = reverse("edit-review", kwargs={'pk': self.object.pk})
        activity_description = 'Review saved'
        activity_type = ActivityLog.TYPES.modify
        if form_action == 'submit':
            activity_description = 'Review submitted'
            activity_type = ActivityLog.TYPES.task
            self.success_url = self.object.reference.get_absolute_url()
            self.object.state = models.Review.STATES.submitted
            data['state'] = models.Review.STATES.submitted

        self.queryset.filter(pk=self.object.pk).update(**data)
        self.object.reference.update_state()
        messages.success(self.request, activity_description)
        ActivityLog.objects.log(self.request, self.object, kind=activity_type, description=activity_description)

    def _valid_approval(self, data, form_action):
        # change review configuration in case anything changed

        if form_action == "save":
            # remove deleted reviews
            preserved_pks = {int(r.get('review')) for r in data['details'].get('reviews', [])}
            self.object.reference.reviews.safety().filter(
                state__lt=models.Review.STATES.submitted
            ).exclude(pk__in=preserved_pks).delete()

            for rev_info in data['details'].pop('additional_reviews', []):
                if not rev_info.get('type'):
                    continue

                rev_type = ReviewType.objects.filter(pk=rev_info.get('type')).first()
                reviewer = User.objects.filter(username__iexact=rev_info.get('reviewer', 'x')).first()
                role = rev_type.role
                if rev_type:
                    models.Review.objects.create(
                        reference=self.object.reference, cycle=self.object.cycle, type=rev_type,
                        state=models.Review.STATES.open, form_type=rev_type.form_type, role=role,
                        reviewer=reviewer,
                        due_date=self.object.due_date
                    )
            self.object.reference.update_due_dates()

        elif form_action == 'submit':
            risk_level = data['details'].get('risk_level', 0)
            if risk_level < 4:
                # only modify samples if we are approving the material
                safety_reviews = self.object.reference.reviews.safety()

                hazards = defaultdict(set)
                keywords = defaultdict(dict)
                perms = defaultdict(lambda: defaultdict(list))
                controls = set()
                ethics = defaultdict(dict)
                req_types = defaultdict(list)
                equipment_decisions = defaultdict(set)
                rejected = set()

                for rev in safety_reviews:
                    controls |= set(map(int, rev.details.get('controls', [])))
                    for sample in rev.details.get('samples', []):
                        if sample.get('rejected'):
                            rejected.add(sample['sample'])
                        key = int(sample['sample'])
                        ethics[key].update(sample.get('ethics', {}))
                        hazards[key] |= set(sample.get('hazards', []))
                        keywords[key].update(sample.get('keywords', {}))
                        for code, kind in list(sample.get('permissions', {}).items()):
                            perms[key][code].append(kind)
                    for code, kind in list(rev.details.get('requirements', {}).items()):
                        req_types[code].append(kind)

                    for eq in rev.details.get('equipment', []):
                        if 'decision' in eq:
                            equipment_decisions[eq['name']].add(eq['decision'])

                permissions = {k: min(v) for k, v in list(req_types.items())}
                equipment = self.object.reference.equipment

                for k, v in list(equipment_decisions.items()):
                    if len(v) > 1 and 'safe' in v:
                        v.remove('safe')
                    equipment[k]['decision'] = list(v)

                samples = {k: list(v) for k, v in list(hazards.items()) if v}
                for project_sample in self.object.reference.project_samples.all():
                    sample = project_sample.sample
                    sample.hazards.add(*samples.get(sample.pk, []))
                    if sample.pk in keywords:
                        sample.details['keywords'] = keywords.get(sample.pk)
                    if sample.pk in ethics:
                        sample.details['ethics'] = ethics.get(sample.pk)
                        if ethics[sample.pk].get('expiry'):
                            project_sample.expiry = ethics[sample.pk]['expiry']
                    if sample.pk in perms:
                        sample.details['permissions'] = {k: min(v) for k, v in list(perms[sample.pk].items())}
                    if sample.pk not in rejected:
                        sample.is_editable = False
                        project_sample.state = project_sample.STATES.approved
                    else:
                        project_sample.state = project_sample.STATES.rejected
                    project_sample.save()
                    sample.save()

                self.object.reference.controls.add(*controls)
                self.object.reference.state = self.object.reference.STATES.approved
                self.object.reference.permissions = permissions
                self.object.reference.equipment = equipment
            else:
                from projects.models import ProjectSample
                self.object.reference.state = self.object.reference.STATES.denied
                # mark all project samples as rejected
                self.object.reference.project_samples.update(state=ProjectSample.STATES.rejected)
            self.object.reference.risk_level = risk_level
            self.object.reference.save()
            self.object.reference.reviews.update(state=models.Review.STATES.closed)

            # lock all new attachments
            self.object.reference.project.attachments.filter(is_editable=True).update(is_editable=False)

    def form_valid(self, form):
        data = form.cleaned_data
        form_action = data['details']['form_action']
        self.object.modified = timezone.now()
        errors = self.object.validate(data['details']).get('pages')
        progress = self.object.get_progress(data['details'])
        data['is_complete'] = (progress['required'] > 99 and not errors)
        data['modified'] = timezone.now()

        if self.object.type.score_fields:
            total_score = 0.0
            for field, weight in self.object.type.score_fields.items():
                total_score += data['details'].get(field, 0.0) * weight
            data['score'] = total_score

        self._valid_review(data, form_action)
        if self.object.type.code == USO_SAFETY_APPROVAL:
            self._valid_approval(data, form_action)

        return HttpResponseRedirect(self.success_url)

    def get_initial(self, *args, **kwargs):
        initial = super().get_initial()
        safety_types = ReviewType.objects.safety()
        approval_types = ReviewType.objects.safety_approval()
        if self.object.type in safety_types:
            initial['samples'] = [
                {
                    "sample": sample.pk,
                    "hazards": sample.hazards.values_list('pk', flat=True), "keywords": {},
                }
                for sample in self.object.reference.get_samples()
            ]

        elif self.object.type in approval_types:
            samples = {
                sample.pk: {
                    'sample': sample.pk,
                    'hazards': [],
                    'permissions': defaultdict(list),
                    'keywords': {},
                    'decision': [],
                    'expiry': [],
                    'rejected': [],
                }
                for sample in self.object.reference.get_samples()
            }
            # Combine information from completed reviews
            req_types = defaultdict(list)
            for r in self.object.reference.reviews.safety():
                try:
                    for s in r.details.get('samples', []):
                        samples[s['sample']]['hazards'] += s.get('hazards', [])
                        samples[s['sample']]['keywords'].update(s.get('keywords', {}))
                        samples[s['sample']]['decision'].append(s.get('decision', None))
                        for code, kind in s.get('permissions', {}).items():
                            samples[s['sample']]['permissions'][code].append(kind)
                except:
                    pass

                temp_requirements = r.details.get('requirements', {})
                if temp_requirements and isinstance(temp_requirements, dict):
                    for code, kind in temp_requirements.items():
                        req_types[code].append(kind)

            initial['requirements'] = {k: min(v) for k, v in req_types.items()}
            initial['samples'] = [
                {
                    'sample': info['sample'],
                    'hazards': list(set(info['hazards'])),
                    'keywords': info['keywords'],
                    'permissions': {k: min(v) for k, v in info['permissions'].items()},
                    'decision': select_ethics_decision(info['decision']),
                    'expiry': '' if not info['expiry'] else max(info['expiry']),
                    'rejected': any(info['rejected']),
                }
                for info in samples.values()
            ]
            initial['reviews'] = [
                {'review': rev.pk, 'completed': rev.is_complete}
                for rev in self.object.reference.reviews.safety()
            ]
        return initial


class ReviewCycleDetail(RolePermsViewMixin, detail.DetailView):
    template_name = "proposals/cycle-detail.html"
    model = models.ReviewCycle
    admin_roles = USO_ADMIN_ROLES
    allowed_roles = USO_ADMIN_ROLES + USO_MANAGER_ROLES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tracks'] = models.ReviewTrack.objects.all().order_by('acronym')
        context['next_cycle'] = models.ReviewCycle.objects.next(self.object.start_date)
        context['prev_cycle'] = models.ReviewCycle.objects.prev(self.object.start_date)
        context['timeline_width'] = (self.object.end_date - self.object.start_date).days
        context['timeline_tick'] = (self.object.end_date - self.object.start_date).days
        return context


class EditConfig(RolePermsViewMixin, ModalUpdateView):
    form_class = forms.FacilityConfigForm
    model = models.FacilityConfig
    allowed_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        config = self.get_object()
        return super().check_allowed() or config.facility.is_admin(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['delete_url'] = reverse('delete-facility-config', kwargs=self.kwargs)
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        config = self.get_object()
        initial['configs'] = {(t.technique.pk, t.track.pk) for t in config.items.all()}
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        configs = data.pop('configs', [])
        configs_set = set(configs)
        items_set = {
            (i.technique.pk, i.track.pk) for i in self.object.items.all()
        }

        # remove deleted items
        to_delete = items_set - configs_set
        for tech, track in to_delete:
            self.object.items.filter(technique_id=tech, track_id=track).delete()

        # add new entries
        new_items = []
        for tech, track in configs_set - items_set:
            new_items.append(models.ConfigItem(technique_id=tech, config=self.object, track_id=track))
        models.ConfigItem.objects.bulk_create(new_items)

        # save configuration
        data['modified'] = timezone.localtime(timezone.now())
        models.FacilityConfig.objects.filter(pk=self.object.pk).update(**data)
        msg = f"Configuration modified. {len(to_delete)} techniques deleted, {len(new_items)} added."
        messages.success(
            self.request, msg
        )
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.modify, description=msg
        )
        return JsonResponse({"url": ""})


class AddFacilityConfig(RolePermsViewMixin, ModalCreateView):
    form_class = forms.FacilityConfigForm
    model = models.FacilityConfig
    allowed_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        self.facility = models.Facility.objects.get(acronym=self.kwargs['slug'])
        return super().check_allowed() or self.facility.is_admin(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        config = self.facility.configs.last()
        if config:
            initial['accept'] = config.accept
            initial['cycle'] = models.ReviewCycle.objects.filter(open_date__gt=timezone.now()).first()
            initial['comments'] = config.comments
            initial['facility'] = self.facility
            initial['configs'] = {(t.technique.pk, t.track.pk) for t in config.items.all()}
        else:
            initial['accept'] = True
            initial['cycle'] = models.ReviewCycle.objects.filter(open_date__gt=timezone.now()).first()
            initial['comments'] = ""
            initial['facility'] = self.facility
            initial['configs'] = set()
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        configs = data.pop('configs', set())
        # save configuration
        config = models.FacilityConfig.objects.create(**data)
        configs_set = set(configs)
        items_set = {
            (i.technique.pk, i.track.pk) for i in config.items.all()
        }

        # add new entries
        new_items = []
        for tech, track in configs_set - items_set:
            new_items.append(models.ConfigItem(technique_id=tech, config=config, track_id=track))
        models.ConfigItem.objects.bulk_create(new_items)

        # save configuration
        data['modified'] = timezone.localtime(timezone.now())
        models.FacilityConfig.objects.filter(pk=config.pk).update(**data)
        msg = f"New configuration with {len(new_items)} items added."
        messages.success(
            self.request, msg
        )
        ActivityLog.objects.log(
            self.request, config, kind=ActivityLog.TYPES.create, description=msg
        )
        return JsonResponse({"url": ""})


class DeleteConfig(RolePermsViewMixin, ModalDeleteView):
    model = models.FacilityConfig
    allowed_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        config = self.get_object()
        return super().check_allowed() or config.facility.is_admin(self.request.user)


class FacilityOptions(RolePermsViewMixin, View):
    def get(self, *args, **kwargs):
        cycle = None
        if self.request.GET.get('cycle'):
            cycle = models.ReviewCycle.objects.filter(pk=self.request.GET.get('cycle')).first()
        technique_matrix = utils.get_techniques_matrix(cycle)
        return JsonResponse(technique_matrix)


class TechniquesMatrix(RolePermsViewMixin, View):
    def get(self, *args, **kwargs):
        cycle = None
        if self.request.GET.get('cycle'):
            cycle = models.ReviewCycle.objects.filter(pk=self.request.GET.get('cycle')).first()
        technique_matrix = utils.get_techniques_matrix(cycle)
        return JsonResponse(technique_matrix)


class CycleInfo(RolePermsViewMixin, detail.DetailView):
    template_name = 'proposals/fields/cycle-info.html'
    model = models.ReviewCycle

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context['timeline_width'] = (self.object.end_date - self.object.start_date).days / 2
        return context


class ReviewCycleList(RolePermsViewMixin, ItemListView):
    model = models.ReviewCycle
    template_name = "item-list.html"
    list_columns = ['name', 'id', 'state', 'start_date', 'open_date', 'close_date', 'num_submissions', 'num_facilities']
    list_filters = ['start_date']
    link_url = "review-cycle-detail"
    list_search = ['start_date', 'open_date', 'close_date', 'alloc_date', 'due_date']
    order_by = ['-start_date']
    admin_roles = USO_ADMIN_ROLES
    allowed_roles = USO_ADMIN_ROLES


class EditReviewCycle(SuccessMessageMixin, RolePermsViewMixin, ModalUpdateView):
    form_class = forms.ReviewCycleForm
    model = models.ReviewCycle
    allowed_roles = USO_ADMIN_ROLES

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_success_url(self):
        success_url = reverse("review-cycle-detail", kwargs={'pk': self.object.pk})
        return success_url

    def form_valid(self, form):
        super().form_valid(form)
        return JsonResponse(
            {
                "url": self.get_success_url()
            }
        )


class AddReviewStage(RolePermsViewMixin, ModalCreateView):
    form_class = forms.ReviewStageForm
    model = models.ReviewStage
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def get_initial(self):
        initial = super().get_initial()
        track = models.ReviewTrack.objects.get(acronym=self.kwargs['track'])
        initial.update(track=track, position=(track.stages.count() + 1), pass_score=4.0)
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        models.ReviewStage.objects.create(**data)
        return JsonResponse({"url": ""})


class EditReviewStage(RolePermsViewMixin, ModalUpdateView):
    form_class = forms.ReviewStageForm
    model = models.ReviewStage
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['delete_url'] = reverse("delete-review-stage", kwargs=self.kwargs)
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        models.ReviewStage.objects.filter(pk=self.object.pk).update(**data)
        return JsonResponse({"url": ""})


class DeleteReviewStage(RolePermsViewMixin, ModalDeleteView):
    model = models.ReviewStage
    allowed_roles = USO_ADMIN_ROLES


class SubmissionList(RolePermsViewMixin, ItemListView):
    model = models.Submission
    template_name = "item-list.html"
    list_columns = ['title', 'code', 'spokesperson', 'cycle', 'pool', 'facilities', 'state']
    list_filters = ['created', 'state', 'track', 'pool', 'cycle']
    list_search = ['proposal__title', 'proposal__id', 'proposal__spokesperson__last_name', 'proposal__keywords']
    link_url = "submission-detail"
    order_by = ['-cycle_id']
    list_title = 'Submitted Proposals'
    list_transforms = {
        'facilities': _fmt_beamlines,
        'title': utils.truncated_title
    }
    list_styles = {'title': 'col-sm-2'}
    admin_roles = USO_ADMIN_ROLES
    paginate_by = 25

    def get_queryset(self, *args, **kwargs):
        qset = super().get_queryset(*args, **kwargs)
        if not self.check_admin():
            qset = qset.filter(reviews__reviewer=self.request.user).distinct()
        return qset

    def get_link_url(self, obj):
        if self.check_admin():
            return reverse("submission-detail", kwargs={'pk': obj.pk})
        else:
            return None


class UserSubmissionList(RolePermsViewMixin, ItemListView):
    model = models.Submission
    template_name = "item-list.html"
    list_columns = ['title', 'code', 'spokesperson', 'cycle', 'pool', 'facilities', 'state']
    list_filters = ['created', 'state', 'track', 'pool', 'cycle']
    list_search = ['proposal__title', 'proposal__id', 'proposal__spokesperson__last_name', 'proposal__keywords']
    link_url = "submission-detail"
    order_by = ['-cycle_id']
    list_title = 'My Submitted Proposals'
    list_transforms = {
        'facilities': _fmt_beamlines,
        'title': utils.truncated_title
    }
    list_styles = {'title': 'col-sm-2'}
    admin_roles = USO_ADMIN_ROLES
    paginate_by = 25

    def get_queryset(self, *args, **kwargs):
        queryset = super().get_queryset(*args, **kwargs)
        user = self.request.user
        flt = Q(proposal__leader_username=user.username) | Q(proposal__spokesperson=user) | Q(proposal__delegate_username=user.username)
        return queryset.filter(flt).distinct()


class CycleSubmissionList(SubmissionList):
    def get_queryset(self, *args, **kwargs):
        qset = super().get_queryset(*args, **kwargs)
        qset = qset.filter(cycle_id=self.kwargs['cycle'])
        return qset


class TrackSubmissionList(CycleSubmissionList):
    def get_queryset(self, *args, **kwargs):
        qset = super().get_queryset(*args, **kwargs)
        qset = qset.filter(track__acronym=self.kwargs['track'])
        return qset


class FacilitySubmissionList(RolePermsViewMixin, ItemListView):
    model = models.Submission
    template_name = "item-list.html"
    list_columns = ['code', 'title', 'spokesperson', 'cycle', 'pool', 'facilities', 'state']
    list_filters = ['created', 'state', 'track', 'pool']
    list_search = ['proposal__title', 'proposal__id', 'proposal__spokesperson__last_name', 'proposal__keywords']
    link_url = "submission-detail"
    order_by = ['-cycle_id']
    list_title = 'Proposal Submissions'
    list_transforms = {
        'facilities': _fmt_beamlines,
        'title': utils.truncated_title,
        'proposal__spokesperson': utils.user_format

    }

    list_styles = {'title': 'col-sm-2'}
    admin_roles = USO_ADMIN_ROLES
    allowed_roles = USO_ADMIN_ROLES

    def get_list_title(self):
        return '{} Submissions'.format(self.facility.acronym)

    def check_allowed(self):
        from beamlines.models import Facility
        self.facility = Facility.objects.get(acronym=self.kwargs['slug'])
        allowed = (super().check_allowed() or self.facility.is_staff(self.request.user))
        return allowed

    def get_queryset(self, *args, **kwargs):
        queryset = models.Submission.objects.all()
        if self.kwargs.get('cycle'):
            queryset = queryset.filter(cycle=self.kwargs['cycle'])
        queryset = queryset.filter(
            techniques__config__facility__acronym=self.kwargs['slug']
        ).order_by().distinct()
        self.queryset = queryset
        return super().get_queryset(*args, **kwargs)


def _name_list(l, obj=None):
    return ", ".join([t.name for t in l.all()])


def _acronym_list(l, obj=None):
    return ", ".join([t.acronym for t in l.all()])


def _adjusted_score(val, obj=None):
    if val:
        col = "progress-bar-success" if val > 0 else "progress-bar-danger"
        return '<span class="label {}">{:+}</span>'.format(col, val)
    else:
        return ""


class ReviewEvaluationList(RolePermsViewMixin, ItemListView):
    model = models.Submission
    template_name = "item-list.html"
    list_filters = ['created', 'pool', 'techniques__config__facility']
    list_search = ['proposal__title', 'proposal__id', 'proposal__team', 'proposal__keywords']
    link_url = "submission-detail"
    order_by = ['proposal__id', '-cycle_id', '-stdev']
    list_title = 'Review Evaluation'
    list_transforms = {
        'facilities': _acronym_list, 'adj': _adjusted_score,
    }
    paginate_by = 25
    admin_roles = USO_ADMIN_ROLES
    allowed_roles = USO_ADMIN_ROLES

    def get_list_columns(self):
        track = models.ReviewTrack.objects.filter(acronym=self.kwargs['track']).first()
        review_types = track.stages.values_list('kind__pk', 'kind__code')
        columns = ['proposal', 'code', 'facilities', 'reviewer']
        for pk, code in review_types:
            columns.extend([f'{code}_avg', f'{code}_std'])
        columns.append('adj')
        return columns

    def get_list_transforms(self):
        transforms = {**self.list_transforms}
        for rev_type in ReviewType.objects.scored():
            transforms.update(
                {
                    f'{rev_type.code}_avg': utils.score_format,
                    f'{rev_type.code}_std': utils.stdev_format
                }
            )
        return transforms

    def get_queryset(self, *args, **kwargs):
        queryset = super().get_queryset(*args, **kwargs)
        queryset = queryset.filter(state__gte=models.Submission.STATES.reviewed)
        queryset = queryset.filter(cycle_id=self.kwargs['cycle'], track__acronym=self.kwargs['track']).with_scores()
        return queryset


class SubmissionDetail(RolePermsViewMixin, detail.DetailView):
    template_name = "proposals/submission-detail.html"
    model = models.Submission
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def check_owner(self, obj):
        return (
            self.request.user.username in [
            obj.proposal.spokesperson.username, obj.proposal.delegate_username, obj.proposal.leader_username
        ])

    def get_queryset(self):
        return self.model.objects.with_scores()

    def check_allowed(self):
        submission = self.get_object()
        reviewer = self.request.user.reviewer if hasattr(self.request.user, 'reviewer') else None
        is_committee = reviewer and reviewer.committee == submission.track
        is_committee_reviewer = is_committee and submission.reviews.filter(reviewer=self.request.user).exists()
        is_facility_admin = any(fac.is_admin(self.request.user) for fac in submission.facilities())
        return (
                super().check_allowed() or
                self.check_admin() or
                self.check_owner(submission) or
                is_facility_admin or
                is_committee_reviewer
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        population = self.object.get_score_distribution()
        scores = self.object.scores()
        stage_results = {}
        for stage in self.object.track.stages.all():
            stage_scores = scores.get(stage, {})
            stage_population = population.get(stage, [])

            if not stage_scores:
                continue

            debug_value(population)

            if stage.kind.per_facility:
                stage_results[stage] = {
                    acronym: {
                        'score': facility_scores['score_avg'],
                        'stdev': facility_scores['score_std'],
                        'passed': facility_scores.get('passed'),
                        'rank': int(100 - percentileofscore(stage_population, facility_scores.get('score_avg', 0))),
                    }
                    for acronym, facility_scores in stage_scores.items()
                }
            else:
                stage_results[stage] = {
                    'score': stage_scores['score_avg'],
                    'stdev': stage_scores['score_std'],
                    'passed': stage_scores.get('passed'),
                    'rank': int(100 - percentileofscore(stage_population, stage_scores.get('score_avg', 0))),
                }

        reviewer = self.request.user.reviewer if hasattr(self.request.user, 'reviewer') else None
        is_committee = reviewer and reviewer.committee == self.object.track
        is_committee_reviewer = is_committee and self.object.reviews.filter(reviewer=self.request.user).exists()

        context['stage_results'] = stage_results
        context['facility_requests'] = self.object.get_requests()
        context['committee_member'] = is_committee_reviewer
        return context


class ReviewerList(RolePermsViewMixin, ItemListView):
    template_name = "item-list.html"
    model = models.Reviewer
    paginate_by = 15
    list_filters = ['modified', 'user__classification', 'active']
    list_columns = ['user', 'institution', 'topic_names']
    list_search = ['user__first_name', 'user__last_name', 'user__email']
    link_url = 'edit-reviewer-profile'
    ordering = ['-created']
    allowed_roles = USO_ADMIN_ROLES


class AddReviewCycles(RolePermsViewMixin, ModalConfirmView):
    template_name = "proposals/forms/create-cycle.html"
    model = models.ReviewCycle
    allowed_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        cycle = self.get_object()
        return reverse('review-cycle-detail', kwargs={'pk': cycle.pk})

    def confirmed(self, *args, **kwargs):
        current_cycle = self.get_object()
        utils.create_cycle(current_cycle.end_date)
        next_cycle = models.ReviewCycle.objects.next(current_cycle.start_date)

        ActivityLog.objects.log(
            self.request, current_cycle, kind=ActivityLog.TYPES.create, description='Cycles created'
        )
        self.success_url = reverse('review-cycle-detail', kwargs={'pk': next_cycle.pk})
        return JsonResponse({"url": self.success_url})


class AssignReviewers(RolePermsViewMixin, ModalConfirmView):
    template_name = "proposals/forms/assign.html"
    model = models.ReviewCycle
    allowed_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        cycle = self.get_object()
        stage = models.ReviewStage.objects.get(pk=self.kwargs.get('stage'))
        return reverse('assigned-reviewers', kwargs={'cycle': cycle.pk, 'stage': stage.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cycle = models.ReviewCycle.objects.get(pk=self.kwargs.get('pk'))
        stage = models.ReviewStage.objects.get(pk=self.kwargs.get('stage'))
        context['cycle'] = cycle
        context['stage'] = stage
        return context

    def confirmed(self, *args, **kwargs):
        cycle = models.ReviewCycle.objects.filter(state=models.ReviewCycle.STATES.assign).get(pk=self.kwargs.get('pk'))
        stage = models.ReviewStage.objects.get(pk=self.kwargs.get('stage'))

        # assign reviewers and prc members
        assignment, success = utils.assign_reviewers(cycle, stage)

        if success:
            # remove all currently assigned pending reviews for this stage
            stage.reviews.all().delete()
            to_create = []

            for submission, reviewers in assignment.items():
                to_create.extend(
                    [
                        models.Review(
                            reviewer=u.user, reference=submission, type=stage.kind, cycle=submission.cycle,
                            form_type=stage.kind.form_type, due_date=cycle.due_date, stage=stage
                        ) for u in reviewers
                    ]
                )

            messages.success(self.request, 'Reviewer assignment successful')
            models.Review.objects.bulk_create(to_create)
            ActivityLog.objects.log(
                self.request, stage, kind=ActivityLog.TYPES.task, description='Reviewers Assigned'
            )
        else:
            messages.error(self.request, 'No feasible reviewer assignment was found')
        return JsonResponse({"url": self.get_success_url()})


class ReviewCompatibility(RolePermsViewMixin, detail.DetailView):
    model = models.Review
    template_name = "proposals/review-compat.html"
    admin_roles = USO_ADMIN_ROLES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        review = self.get_object()
        cycle = review.cycle

        if hasattr(review.reviewer, 'reviewer'):
            user = review.reviewer
            reviewer = user.reviewer

            context['compat_techniques'] = reviewer.techniques.filter(
                pk__in=review.reference.techniques.values_list('technique', flat=True)
            )
            context['compat_areas'] = reviewer.areas.all() & review.reference.proposal.areas.all()
            context['conflict'] = utils.has_conflict(review.reference, reviewer)
            context['workload'] = user.reviews.filter(cycle=cycle)
            context['reviewer'] = reviewer
            context['submission'] = review.reference
        return context


class AssignedSubmissionList(RolePermsViewMixin, ItemListView):
    model = models.Submission
    template_name = "proposals/assignment-list.html"
    paginate_by = 5
    list_columns = ['proposal', 'cycle', 'track', 'state']
    list_filters = ['created', 'state', 'track', 'cycle']
    list_search = ['proposal__title', 'proposal__id', 'proposal__team', 'proposal__keywords',
                   'proposal__spokesperson__last_name']
    link_url = "submission-detail"
    list_styles = {'proposal': 'col-sm-6'}
    order_by = ['-cycle__start_date', '-created']
    list_title = 'Reviewer Assignments'
    allowed_roles = USO_ADMIN_ROLES

    def get_queryset(self, *args, **kwargs):
        self.stage = models.ReviewStage.objects.get(pk=self.kwargs['stage'])
        self.cycle = models.ReviewCycle.objects.get(pk=self.kwargs['cycle'])
        self.queryset = self.cycle.submissions.filter(track=self.stage.track).all()
        return super().get_queryset(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cycle'] = self.cycle
        context['stage'] = self.stage
        return context


class ReviewerAssignments(RolePermsViewMixin, ItemListView):
    model = models.Submission
    template_name = "item-list.html"
    paginate_by = 20
    list_columns = ['proposal', 'cycle', 'track', 'state']
    list_filters = ['created', 'state', 'track', 'cycle']
    list_search = ['proposal__title', 'proposal__id', 'proposal__team', 'proposal__keywords',
                   'proposal__spokesperson__last_name']
    link_url = "submission-detail"
    list_styles = {'proposal': 'col-sm-6'}
    order_by = ['-cycle__start_date', '-created']
    list_title = 'Reviewer Assignments'
    allowed_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        allowed = super().check_allowed()
        if not allowed and hasattr(self.request.user, 'reviewer'):
            reviewer = self.request.user.reviewer
            allowed = reviewer and reviewer.active and reviewer.committee
        return allowed

    def get_queryset(self, *args, **kwargs):
        self.reviewer = models.Reviewer.objects.get(pk=self.kwargs['pk'])
        self.cycle = models.ReviewCycle.objects.get(pk=self.kwargs['cycle'])
        self.queryset = self.reviewer.committee_proposals(self.cycle)
        return super().get_queryset(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cycle'] = self.cycle
        context['reviewer'] = self.reviewer
        return context

    def get_list_title(self):
        return f'{self.reviewer.user} ~ {self.cycle}'


class PRCAssignments(RolePermsViewMixin, ItemListView):
    model = models.Submission
    template_name = "item-list.html"
    paginate_by = 20
    list_columns = ['proposal', 'cycle', 'track', 'state']
    list_filters = ['created', 'state', 'track', 'cycle']
    list_search = ['proposal__title', 'proposal__id', 'proposal__team', 'proposal__keywords',
                   'proposal__spokesperson__last_name']
    link_url = "submission-detail"
    list_styles = {'proposal': 'col-sm-6'}
    order_by = ['-cycle__start_date', '-created']
    list_title = 'Committee Assignments'
    allowed_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        allowed = super().check_allowed()
        if not allowed and hasattr(self.request.user, 'reviewer'):
            reviewer = self.request.user.reviewer
            allowed = reviewer and reviewer.active and reviewer.committee
        return allowed

    def get_queryset(self, *args, **kwargs):
        reviewer = models.Reviewer.objects.filter(user=self.request.user).first()
        if not reviewer:
            self.queryset = self.model.objects.none()
        else:
            cycle = models.ReviewCycle.objects.next()
            self.queryset = reviewer.committee_proposals(cycle)
        return super().get_queryset(*args, **kwargs)


class ReviewerOptOut(RolePermsViewMixin, ModalUpdateView):
    model = models.Reviewer
    form_class = forms.OptOutForm
    success_url = reverse_lazy("user-dashboard")
    allowed_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        allowed = super().check_allowed()
        if not allowed:
            reviewer = self.get_object()
            allowed = self.request.user == reviewer.user
        return allowed

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        messages.success(self.request, 'You have successfully opted out of the next round of reviews.')
        self.object.declined = timezone.now().date()
        self.object.save()
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.task,
            description=f'Reviewer opted out: {data["comments"]}'
        )
        return JsonResponse({"url": self.get_success_url()})


class AddReviewAssignment(RolePermsViewMixin, ModalUpdateView):
    form_class = forms.ReviewerAssignmentForm
    model = models.Submission
    allowed_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        allowed = super().check_allowed()
        if not allowed:
            submission = self.get_object()
            if hasattr(self.request.user, 'reviewer'):
                reviewer = self.request.user.reviewer
                allowed = (
                        reviewer and reviewer.active and reviewer.committee == submission.track and
                        submission.reviews.filter(reviewer=reviewer.user).scientific().exists()
                )
        return allowed

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['stage'] = models.ReviewStage.objects.get(pk=self.kwargs['stage'])
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        stage = models.ReviewStage.objects.get(pk=self.kwargs['stage'])
        if data['reviewers'].filter(committee__isnull=False).exists():
            self.object.reviews.filter(stage=stage, reviewer__reviewer__committee__isnull=False).delete()
            messages.success(self.request, "Committee members were swapped.")

        if stage.kind:
            to_add = [
                models.Review(
                    reviewer=rev.user, cycle=self.object.cycle, reference=self.object,
                    due_date=self.object.cycle.due_date, stage=stage,
                    type=stage.kind, state=models.Review.STATES.pending, form_type=stage.kind.form_type
                ) for rev in data['reviewers']
            ]
            models.Review.objects.bulk_create(to_add)
            messages.success(self.request, "Reviews were added")
            ActivityLog.objects.log(
                self.request, self.object, kind=ActivityLog.TYPES.modify, description='Reviewers added'
            )
        return JsonResponse({"url": ""})


class DeleteReview(RolePermsViewMixin, ModalDeleteView):
    model = models.Review
    allowed_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        allowed = super().check_allowed()
        review = self.get_object()
        if not allowed:
            if hasattr(self.request.user, 'reviewer'):
                reviewer = self.request.user.reviewer
                allowed = (
                        reviewer and reviewer.active and reviewer.committee == review.reference.track
                        and review.reference.reviews.filter(reviewer=reviewer.user).scientific().exists()
                )
        return allowed and review.reviewer != self.request.user

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.model.objects.filter(state=self.model.STATES.pending)
        return super().get_queryset(*args, **kwargs)


class ShowClarifications(RolePermsViewMixin, detail.DetailView):
    model = models.Proposal
    template_name = 'proposals/clarifications.html'


class ShowAttachments(RolePermsViewMixin, detail.DetailView):
    model = models.Proposal
    template_name = 'proposals/attachments.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class AnswerClarification(ClarificationResponse):
    reference_model = models.Proposal

    def check_allowed(self):
        proposal = self.get_reference()
        if not proposal:
            return False
        else:
            return (
                    (self.request.user == proposal.spokesperson) or
                    (self.request.user.username in [proposal.delegate_username, proposal.leader_username])
            )

    def form_valid(self, form):
        response = super().form_valid(form)
        proposal = self.get_reference()

        review_ids = proposal.submissions.filter(
            Q(state__lt=models.Submission.STATES.reviewed) & (Q(reviews__reviewer=self.object.requester) | (
                    Q(reviews__reviewer__isnull=True) & Q(reviews__role__in=self.object.requester.roles)))
        ).values_list('reviews', flat=True)
        reviews = models.Review.objects.filter(pk__in=review_ids)

        recipients = [self.object.requester]
        data = {
            'title': proposal.title, 'clarification': self.object.question, 'response': self.object.response,
            'reviews': reviews,
        }
        notify.send(recipients, 'clarification-received', level=notify.LEVELS.important, context=data)
        return response


class AskClarification(RequestClarification):
    reference_model = models.Proposal

    def form_valid(self, form):
        response = super().form_valid(form)
        proposal = self.get_reference()
        success_url = reverse_lazy('proposal-detail', kwargs={'pk': proposal.pk})
        full_url = "{}{}".format(getattr(settings, 'SITE_URL', ""), success_url)
        for member in proposal.get_full_team():
            user = proposal.get_member(member)
            if not member.get('roles'):
                continue
            recipients = [user] if user else [member['email']]
            data = {
                'name': "{first_name} {last_name}".format(**member) if not user else user.get_full_name(),
                'title': proposal.title, 'clarification': self.object.question, 'respond_url': full_url,
                'due_date': timezone.now().date() + timedelta(days=3),
            }
            notify.send(recipients, 'clarification-requested', level=notify.LEVELS.important, context=data)
        return response


class ReviewerOptions(RolePermsViewMixin, TemplateView):
    template_name = 'proposals/fields/options.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role = self.request.GET.get('role', '')
        candidates = User.objects.all_with_roles(role)
        reviewer = self.request.GET.get('reviewer', '')
        selected = get_user_model().objects.filter(username=reviewer).first()

        if role:
            context['options'] = [('', role.replace('-', ' ').title() + ' Role', True)] + [
                (user.username, user, user == selected) for user in candidates]
        else:
            context['options'] = []
        return context


class StartReviews(RolePermsViewMixin, ModalConfirmView):
    template_name = "proposals/forms/reviews.html"
    model = models.ReviewStage
    allowed_roles = USO_ADMIN_ROLES

    def confirmed(self, *args, **kwargs):
        stage = self.get_object()
        cycle = models.ReviewCycle.objects.filter(pk=self.kwargs.get('cycle')).first()
        if cycle and stage:
            # gather relevant reviews
            reviews = models.Review.objects.filter(cycle=cycle, stage=stage, state=models.Review.STATES.pending)
            utils.notify_reviewers(reviews)
            reviews.update(state=models.Review.STATES.open)
            ActivityLog.objects.log(
                self.request, cycle, kind=ActivityLog.TYPES.modify,
                description=f'Cycle {cycle}: Reviews for {stage.track} stage-{stage.position} started'
            )
        return JsonResponse({"url": ""})


class StatsDataAPI(RolePermsViewMixin, TemplateView):
    admin_roles = USO_ADMIN_ROLES
    allowed_roles = USO_STAFF_ROLES

    def get(self, *args, **kwargs):
        from . import stats
        tables = stats.get_proposal_stats()
        return JsonResponse(tables[1].series())


class Statistics(RolePermsViewMixin, TemplateView):
    admin_roles = USO_ADMIN_ROLES
    allowed_roles = USO_STAFF_ROLES
    template_name = "proposals/statistics.html"


class AddScoreAdjustment(RolePermsViewMixin, ModalUpdateView):
    form_class = forms.AdjustmentForm
    model = models.Submission
    allowed_roles = USO_ADMIN_ROLES

    def get_delete_url(self):
        obj = self.get_object()
        if hasattr(obj, 'adjustment'):
            return reverse("remove-score-adjustment", kwargs={'pk': obj.pk})
        return None

    def get_initial(self):
        initial = super().get_initial()
        submission = self.get_object()
        if hasattr(submission, 'adjustment'):
            initial['value'] = submission.adjustment.value
            initial['reason'] = submission.adjustment.reason
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        data['user'] = self.request.user
        submission = self.get_object()
        obj, created = models.ScoreAdjustment.objects.update_or_create(submission=submission, defaults=data)
        ActivityLog.objects.log(
            self.request, submission, kind=ActivityLog.TYPES.task,
            description=f'Score Adjusted by {data["value"]}'
        )
        messages.success(self.request, f'Score adjustment of {obj.value} applied to submission')
        return JsonResponse({"url": ""})


class DeleteAdjustment(RolePermsViewMixin, ModalDeleteView):
    model = models.ScoreAdjustment
    allowed_roles = USO_ADMIN_ROLES

    def get_object(self, queryset=None):
        submission = models.Submission.objects.get(pk=self.kwargs['pk'])
        return submission.adjustment

    def confirmed(self, *args, **kwargs):
        self.object = self.get_object()
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.delete, description='Score Adjustment Deleted'
        )
        self.object.delete()
        return JsonResponse({"url": ""})


class UpdateReviewComments(RolePermsViewMixin, ModalUpdateView):
    form_class = forms.ReviewCommentsForm
    model = models.Submission
    allowed_roles = USO_ADMIN_ROLES

    def get_queryset(self):
        return self.model.objects.filter(state__gte=models.Submission.STATES.complete)

    def form_valid(self, form):
        data = form.cleaned_data
        submission = self.get_object()
        submission.comments = data['comments']
        submission.save()
        ActivityLog.objects.log(
            self.request, submission, kind=ActivityLog.TYPES.modify, description='Reviewer comments updated'
        )
        messages.success(self.request, 'Reviewer comments updated')
        return JsonResponse(
            {
                "url": ""
            }
        )


class ReviewTypeList(RolePermsViewMixin, ItemListView):
    model = ReviewType
    template_name = "tooled-item-list.html"
    tool_template = "proposals/review-type-tools.html"
    list_columns = ['description', 'code', 'form_type', 'low_better', 'per_facility']
    list_filters = ['created', 'modified']
    list_search = ['name', 'code', 'description']
    link_url = "edit-review-type"
    link_attr = 'data-modal-url'
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES
    paginate_by = 20


class AddReviewType(RolePermsViewMixin, ModalCreateView):
    form_class = forms.ReviewTypeForm
    model = ReviewType
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        return reverse('review-type-list')


class EditReviewType(RolePermsViewMixin, ModalUpdateView):
    form_class = forms.ReviewTypeForm
    model = ReviewType
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['delete_url'] = reverse("delete-review-type", kwargs=self.kwargs)
        return kwargs

    def get_success_url(self):
        return reverse('review-type-list')

    def form_valid(self, form):
        data = form.cleaned_data
        ReviewType.objects.filter(pk=self.object.pk).update(**data)
        return JsonResponse({"url": self.get_success_url()})


class DeleteReviewType(RolePermsViewMixin, ModalDeleteView):
    model = ReviewType
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        return reverse('review-type-list')


class TechniqueList(RolePermsViewMixin, ItemListView):
    model = models.Technique
    template_name = "tooled-item-list.html"
    tool_template = "proposals/technique-tools.html"
    list_columns = ['name', 'acronym', 'description', 'areas']
    list_filters = ['created', 'modified', 'category']
    list_search = ['name', 'acronym', 'description', 'category', 'parent__name', 'parent__description', 'parent__acronym']
    link_url = "edit-technique"
    link_attr = 'data-modal-url'
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES
    paginate_by = 20


class AddTechnique(RolePermsViewMixin, ModalCreateView):
    form_class = forms.TechniqueForm
    model = models.Technique
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        return reverse('technique-list')


class EditTechnique(RolePermsViewMixin,  ModalUpdateView):
    form_class = forms.TechniqueForm
    model = models.Technique
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['delete_url'] = reverse("delete-technique", kwargs=self.kwargs)
        return kwargs

    def get_success_url(self):
        return reverse('technique-list')

    def form_valid(self, form):
        data = form.cleaned_data
        models.Technique.objects.filter(pk=self.object.pk).update(**data)
        return JsonResponse({"url": self.get_success_url()})


class DeleteTechnique(RolePermsViewMixin, ModalDeleteView):
    model = models.Technique
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        return reverse('technique-list')

    def confirmed(self, *args, **kwargs):
        self.object = self.get_object()
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.delete, description='Technique Deleted'
        )
        self.object.delete()
        return JsonResponse({"url": self.get_success_url()})


class ReviewTrackList(RolePermsViewMixin, ItemListView):
    template_name = "tooled-item-list.html"
    model = models.ReviewTrack
    tool_template = "proposals/track-list-tools.html"
    list_columns = ['name',  'acronym', 'description', 'duration']
    list_filters = ['created', 'modified', 'require_call']
    list_search = ['acronym', 'name', 'committee__last_name', 'description']
    link_url = "edit-review-track"
    link_attr = 'data-modal-url'
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES
    paginate_by = 20


class AddReviewTrack(RolePermsViewMixin, ModalCreateView):
    form_class = forms.ReviewTrackForm
    model = models.ReviewTrack
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES


class EditReviewTrack(RolePermsViewMixin, ModalUpdateView):
    form_class = forms.ReviewTrackForm
    model = models.ReviewTrack
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['delete_url'] = reverse("delete-review-track", kwargs=self.kwargs)
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        track = self.get_object()
        initial.update(committee=track.committee.all())
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        committee = data.pop('committee', [])
        models.ReviewTrack.objects.filter(pk=self.object.pk).update(**data)
        self.object.committee.clear()
        self.object.committee.add(*committee)
        return JsonResponse({"url": "."})


class DeleteReviewTrack(RolePermsViewMixin, ModalDeleteView):
    model = models.ReviewTrack
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        return reverse('review-track-list')

    def confirmed(self, *args, **kwargs):
        self.object = self.get_object()
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.delete, description='Review Track Deleted'
        )
        self.object.delete()
        return JsonResponse({"url": self.get_success_url()})


class AccessPoolList(RolePermsViewMixin, ItemListView):
    template_name = "item-list.html"
    model = models.AccessPool
    list_columns = ['name', 'description', 'role', 'is_default']
    list_filters = ['created', 'modified', 'is_default']
    list_search = ['name', 'description', 'role']
    link_url = "edit-access-pool"
    link_attr = 'data-modal-url'
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES
    paginate_by = 20


class AddAccessPool(RolePermsViewMixin, ModalCreateView):
    form_class = forms.AccessPoolForm
    model = models.AccessPool
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        return reverse('access-pool-list')


class EditAccessPool(RolePermsViewMixin, ModalUpdateView):
    form_class = forms.AccessPoolForm
    model = models.AccessPool
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        obj = self.get_object()
        # Deleting default access pools is not allowed
        if not obj.is_default:
            kwargs['delete_url'] = reverse("delete-access-pool", kwargs=self.kwargs)
        return kwargs

    def get_success_url(self):
        return reverse('access-pool-list')

    def form_valid(self, form):
        data = form.cleaned_data
        models.AccessPool.objects.filter(pk=self.object.pk).update(**data)
        return JsonResponse({"url": self.get_success_url()})


class DeleteAccessPool(RolePermsViewMixin, ModalDeleteView):
    model = models.AccessPool
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        return reverse('access-pool-list')


class EditFacilityPools(RolePermsViewMixin, ModalUpdateView):
    form_class = forms.AllocationPoolForm
    model = models.Facility
    allowed_roles = USO_ADMIN_ROLES
    slug_field = 'acronym'
    success_url = "."

    def check_allowed(self):
        facility = self.get_object()
        return (
            super().check_allowed() or
            facility.is_admin(self.request.user)
        )

    def get_initial(self):
        initial = super().get_initial()
        facility = self.get_object()
        initial['pools'] = {
            pool.pk: percent for pool, percent in facility.access_pools()
        }
        debug_value(initial)
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        pools = data.pop('pools', {})

        self.object.details.update(pools=pools)
        self.object.flex_schedule = data.get('flex_schedule', False)
        self.object.save()
        return JsonResponse({'url': self.get_success_url()})

