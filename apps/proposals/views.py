from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.utils import NestedObjects
from django.contrib.auth import get_user_model
from django.contrib.messages.views import SuccessMessageMixin
from django.db import DEFAULT_DB_ALIAS
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.text import capfirst
from django.views.generic import detail, edit, TemplateView, View
from itemlist.views import ItemListView
from scipy import stats as scipy_stats

from dynforms.views import DynUpdateView, DynCreateView
from misc import filters
from misc.models import ActivityLog
from misc.views import ConfirmDetailView, ClarificationResponse, RequestClarification
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
    return '<i class="icon-1x {0} {1} text-center" title="{2}"></>'.format(
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
        qchain = Q(spokesperson=self.request.user)
        if self.request.user.email:
            qchain |= Q(team__icontains=self.request.user.email)
        if self.request.user.alt_email:
            qchain |= Q(team__icontains=self.request.user.alt_email)

        self.queryset = models.Proposal.objects.filter(qchain)
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

    def get_queryset(self, *args, **kwargs):
        self.queryset = models.Proposal.objects.filter(state=models.Proposal.STATES.draft)
        return super().get_queryset(*args, **kwargs)


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
        return 'Peer-Reviewers - {} Track'.format(self.track)

    def get_detail_url(self, obj):
        return reverse('prc-reviews', kwargs={'cycle': self.cycle.pk, 'pk': obj.pk})

    def get_queryset(self, *args, **kwargs):
        self.track = models.ReviewTrack.objects.get(acronym=self.kwargs['track'])
        self.cycle = models.ReviewCycle.objects.get(pk=self.kwargs['cycle'])
        self.queryset = models.Reviewer.objects.filter(committee=self.track)
        return super().get_queryset(*args, **kwargs)


class CreateProposal(RolePermsViewMixin, DynCreateView):
    model = models.Proposal
    form_class = forms.ProposalForm

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
    model = models.Proposal
    form_class = forms.ProposalForm
    admin_roles = USO_ADMIN_ROLES

    def check_owner(self, obj):
        qchain = Q(leader_username=self.request.user.username) | Q(spokesperson=self.request.user) | Q(
            delegate_username=self.request.user.username
        )
        self.queryset = models.Proposal.objects.filter(state=models.Proposal.STATES.draft).filter(qchain)

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


class CloneProposal(RolePermsViewMixin, ConfirmDetailView):
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
        self.object.title = "[COPY] {0}".format(self.object.title)
        self.object.created = timezone.now()
        self.object.modified = timezone.now()
        self.object.details['active_page'] = 0
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


class SubmitProposal(RolePermsViewMixin, ConfirmDetailView):
    model = models.Proposal
    template_name = "proposals/forms/submit.html"
    success_url = reverse_lazy('user-proposals')

    def get_queryset(self):
        query = (Q(leader_username=self.request.user.username) | Q(spokesperson=self.request.user) | Q(
            delegate_username=self.request.user.username
        ))
        self.queryset = models.Proposal.objects.filter(state=models.Proposal.STATES.draft).filter(query)
        return super().get_queryset()

    def prepare_submission(self, access_mode="user"):
        """
        Determine the available review tracks and submission options for the current user and the proposal's
        instrument requirements.
        :param access_mode:
        :return:
        """
        requirements = self.object.details['beamline_reqs']
        cycle = models.ReviewCycle.objects.get(pk=self.object.details['first_cycle'])

        conf_items = models.ConfigItem.objects.none()
        beamteam = []
        for req in requirements:
            config = models.FacilityConfig.objects.active(d=cycle.start_date).accepting().filter(
                facility__pk=req.get('facility')
            ).last()
            if config:
                acronym = config.facility.acronym.lower()
                beamteam.append(self.request.user.has_role(f'beamteam-member:{acronym}'))
                conf_items |= config.items.filter(technique__in=req.get('techniques', []))

        if cycle.is_closed() or access_mode in ['staff', 'education', 'purchased', 'beamteam']:
            special_track = models.ReviewTrack.objects.filter(special=True).first()
            requests = {special_track: conf_items}
        else:
            requests = {track: items for track, items in list(conf_items.group_by_track().items()) if items.exists()}

        info = {
            "requests": requests, "cycle": cycle, "beamteam": all(beamteam),
            "staff": self.request.user.has_any_role(*USO_STAFF_ROLES),
            "education": self.request.user.has_any_role(*USO_STAFF_ROLES),
            "industrial": self.request.user.has_any_role(*USO_STAFF_ROLES),
        }
        return info

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.prepare_submission())
        return context

    def confirmed(self, *args, **kwargs):
        self.object = super().get_object()
        access_mode = self.request.POST.get('project_type', 'user')
        info = self.prepare_submission(access_mode=access_mode)
        cycle = info["cycle"]

        # create submissions and technical reviews
        review_types = ReviewType.objects.technical()

        to_create = []
        for track, items in list(info['requests'].items()):
            obj = models.Submission.objects.create(
                proposal=self.object, track=track, kind=access_mode, cycle=cycle
            )
            # map acronym to facility in a unique set
            technical_info = {
                (item.config.facility.acronym.lower(), item.config.facility)
                for item in items
            }

            obj.techniques.add(*items)
            obj.save()
            due_date = min(cycle.due_date, timezone.now().date() + timedelta(weeks=2))

            # create review objects for each technical review type, for each facility
            to_create.extend(
                [
                    models.Review(
                        role=review_type.role.format(acronym), cycle=cycle, reference=obj, type=review_type,
                        form_type=review_type.form_type, state=models.Review.STATES.open,
                        due_date=due_date, details={'requirements': {'facility': facility.pk, 'tags': []}}
                    )
                    for acronym, facility in technical_info
                    for review_type in review_types
                ]
            )

        # create review objects for technical
        models.Review.objects.bulk_create(to_create)

        # update state
        self.object.state = self.object.STATES.submitted
        self.object.details['proposal_type'] = access_mode
        self.object.save()

        # lock all attachments
        self.object.attachments.all().update(is_editable=False)

        # notify team members of submitted proposal
        success_url = reverse('proposal-detail', kwargs={'pk': self.object.pk})
        full_url = f"{getattr(settings, 'SITE_URL', '')}{success_url}"

        others = []
        registered_members = []
        for member in self.object.get_full_team():
            user = self.object.get_member(member)
            if not member.get('roles'):
                others.append(member.get('email', '') if not user else user)
                continue
            if user:
                registered_members.append(user)
                recipients = [user]
            else:
                recipients = [member.get('email', '')]
            data = {
                'name': "{first_name} {last_name}".format(**member) if not user else user.get_full_name(),
                'proposal_title': self.object.title, 'is_delegate': 'delegate' in member.get('roles', []),
                'is_leader': 'leader' in member.get('roles', []),
                'is_spokesperson': 'spokesperson' in member.get('roles', []), 'proposal_url': full_url, 'cycle': cycle,
                'spokesperson': self.object.spokesperson,
            }
            notify.send(recipients, 'proposal-submitted', context=data)

        # notify others
        notify.send(
            others, 'proposal-submitted', context={
                'name': "Research Team Member", 'proposal_title': self.object.title, 'is_delegate': False,
                'is_leader': False, 'is_spokesperson': False, 'proposal_url': full_url, 'cycle': cycle,
                'spokesperson': self.object.spokesperson,
            }
        )
        messages.add_message(self.request, messages.SUCCESS, 'Proposal has been submitted.')
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.task, description='Proposal submitted'
        )

        # Add User Role to all register team members who do not have the role
        for user in registered_members:
            user.fetch_profile()
            roles = user.get_all_roles()
            if 'user' not in roles:
                roles |= {'user'}
                user.update_profile(data={'extra_roles': roles})

        return JsonResponse(
            {
                "url": success_url
            }
        )


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


class DeleteProposal(RolePermsViewMixin, edit.DeleteView):
    success_url = reverse_lazy('user-proposals')
    template_name = "proposals/forms/delete.html"
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

    def _delete_formater(self, obj):
        opts = obj._meta
        return f'{capfirst(opts.verbose_name)}: {force_str(obj)}'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        collector = NestedObjects(using=DEFAULT_DB_ALIAS)  # database name
        collector.collect([context['object']])  # list of objects. single one won't do
        context['related'] = collector.nested(self._delete_formater)
        return context

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(self.request, 'Draft proposal has been deleted')
        ActivityLog.objects.log(
            self.request, obj, kind=ActivityLog.TYPES.delete, description='Proposal deleted'
        )
        super().delete(request, *args, **kwargs)
        return JsonResponse(
            {
                "url": self.success_url
            }
        )


class EditReviewerProfile(RolePermsViewMixin, edit.FormView):
    form_class = forms.ReviewerForm
    template_name = "proposals/forms/form.html"
    model = models.Reviewer
    success_message = "Reviewer profile has been updated."
    admin_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        return reverse_lazy("user-dashboard")

    def get_initial(self, *args, **kwargs):
        initial = super().get_initial()
        if self.kwargs.get('pk'):
            reviewer = models.Reviewer.objects.filter(pk=self.kwargs.get('pk')).first()
        else:
            reviewer, created = models.Reviewer.objects.get_or_create(user=self.request.user)

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
            messages.add_message(self.request, messages.SUCCESS, 'Reviewer {} Disabled'.format(reviewer))
        elif self.request.POST.get('submit') == 'enable':
            models.Reviewer.objects.filter(pk=reviewer.pk).update(active=True)
            messages.add_message(self.request, messages.SUCCESS, 'Reviewer {} Re-enabled'.format(reviewer))

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
    list_columns = ['type', 'title', 'role', 'reviewer', 'state', 'due_date']
    list_filters = ['created', 'modified', CycleFilterFactory.new('cycle'),
                    filters.FutureDateListFilterFactory.new('due_date'), 'state', 'type']

    list_search = ['reviewer__last_name', 'reviewer__first_name', 'role']
    link_url = "edit-review"
    ordering = ['state', 'due_date', '-created']
    list_transforms = {'state': _fmt_review_state, 'role': _fmt_role}
    admin_roles = USO_ADMIN_ROLES


class UserReviewList(ReviewList):
    list_title = 'My Reviews'

    def get_queryset(self, *args, **kwargs):
        self.queryset = models.Review.objects.filter(
            state__gt=models.Review.STATES.pending, state__lte=models.Review.STATES.submitted, ).filter(
            Q(reviewer=self.request.user) | Q(role__in=self.request.user.roles)
        )
        return super().get_queryset(*args, **kwargs)


class ClaimReview(RolePermsViewMixin, ConfirmDetailView):
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
        message = 'Review saved successfully'
        activity_description = 'Review saved'
        activity_type = ActivityLog.TYPES.modify
        if form_action == 'submit':
            message = 'Review submitted successfully'
            activity_description = 'Review submitted'
            activity_type = ActivityLog.TYPES.task
            self.success_url = self.object.reference.get_absolute_url()
            self.object.state = models.Review.STATES.submitted
            data['state'] = models.Review.STATES.submitted
        self.queryset.filter(pk=self.object.pk).update(**data)
        messages.success(self.request, message)
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
        data['is_complete'] = True if self.object.validate(data['details']).get('progress') > 95.0 else False
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
            initial['samples'] = [{
                "sample": s.sample.pk, "hazards": s.sample.hazards.values_list('pk', flat=True), "keywords": {},
            } for s in self.object.reference.project_samples.all()]

        elif self.object.type in approval_types:
            # Combine information from completed reviews
            safety_reviews = self.object.reference.reviews.safety()
            hazards = defaultdict(set)
            keywords = defaultdict(dict)
            perms = defaultdict(lambda: defaultdict(list))
            controls = set()
            req_types = defaultdict(list)
            rejected = set()

            for r in safety_reviews:
                controls |= set(map(int, r.details.get('controls', [])))
                for s in r.details.get('samples', []):
                    if s.get('rejected'):  rejected.add(s['sample'])
                    key = int(s['sample'])
                    hazards[key] |= set(s.get('hazards', []))
                    keywords[key].update(s.get('keywords', {}))
                    for code, kind in s.get('permissions', {}).items():
                        perms[key][code].append(kind)
                temp_requirements = r.details.get('requirements', {})
                if temp_requirements and isinstance(temp_requirements, dict):
                    for code, kind in temp_requirements.items():
                        req_types[code].append(kind)

            initial['controls'] = list(controls)
            initial['requirements'] = {k: min(v) for k, v in req_types.items()}
            initial['samples'] = [
                {
                    'sample': s.sample.pk,
                    'hazards': list(hazards.get(s.sample.pk, [])),
                    'keywords': keywords.get(s.sample.pk, {}),
                    'permissions': {k: min(v) for k, v in perms.get(s.sample.pk, {}).items()},
                    'rejected': s.sample.pk in rejected,
                }
                for s in self.object.reference.project_samples.all()
            ]
            initial['reviews'] = [
                {'review': rev.pk, 'completed': rev.is_complete}
                for rev in self.object.reference.reviews.safety()
            ]
        return initial


class ReviewDetail(RolePermsViewMixin, detail.DetailView):
    model = models.Review
    template_name = "proposals/review_detail.html"
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        allowed = super().check_allowed()
        if not allowed:
            obj = self.get_object()
            allowed = (obj.reviewer == self.request.user or self.request.user.has_role(obj.role))
        return allowed


def accumulate(iterator):
    total = 0
    for item in iterator:
        total += item
        yield total


class ReviewCycleDetail(RolePermsViewMixin, detail.DetailView):
    template_name = "proposals/cycle_detail.html"
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


class EditConfig(RolePermsViewMixin, edit.UpdateView):
    form_class = forms.FacilityConfigForm
    template_name = "forms/modal.html"
    model = models.FacilityConfig
    allowed_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        config = self.get_object()
        return (super().check_allowed() or config.facility.is_admin(self.request.user))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        config = self.get_object()
        initial['settings'] = {t.technique.pk: t.track.acronym for t in config.items.all()}
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        settings = data.pop('settings', {})
        settings_set = set(settings.items())
        items_set = {(i.technique.pk, i.track.acronym) for i in self.object.items.all()}
        settings_techniques = set(settings.keys())
        items_techniques = set(x[0] for x in items_set)
        tracks = {t.acronym: t for t in models.ReviewTrack.objects.all()}

        # remove deleted items
        to_delete = items_techniques - settings_techniques
        self.object.items.filter(technique_id__in=to_delete).delete()

        # update changed items
        changed_items = defaultdict(list)
        for pk, acronym in settings_set - items_set:
            changed_items[tracks[acronym]].append(pk)
        for track, pks in list(changed_items.items()):
            self.object.items.filter(technique_id__in=pks).update(track=track)

        # add new entries
        new_items = []
        for pk in settings_techniques - items_techniques:
            new_items.append(models.ConfigItem(technique_id=pk, config=self.object, track=tracks[settings[pk]]))
        models.ConfigItem.objects.bulk_create(new_items)

        # save configuration
        data['modified'] = timezone.localtime(timezone.now())
        models.FacilityConfig.objects.filter(pk=self.object.pk).update(**data)
        msg = "Configuration modified. {} techniques deleted, {} added, and {} updated.".format(
            len(to_delete), len(new_items), len(list(changed_items.keys())), )
        messages.success(
            self.request, msg
        )
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.modify, description=msg
        )
        return JsonResponse({"url": ""})


class AddFacilityConfig(RolePermsViewMixin, edit.CreateView):
    form_class = forms.FacilityConfigForm
    template_name = "forms/modal.html"
    model = models.FacilityConfig
    allowed_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        self.facility = models.Facility.objects.get(pk=self.kwargs['pk'])
        return (super().check_allowed() or self.facility.is_admin(self.request.user))

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
            initial['settings'] = {t.technique.pk: t.track.acronym for t in config.items.all()}
        else:
            initial['accept'] = True
            initial['cycle'] = models.ReviewCycle.objects.filter(open_date__gt=timezone.now()).first()
            initial['comments'] = ""
            initial['facility'] = self.facility
            initial['settings'] = {}
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        settings = data.pop('settings', {})
        tracks = {t.acronym: t for t in models.ReviewTrack.objects.all()}
        # save configuration
        config = models.FacilityConfig.objects.create(**data)

        # add new entries
        new_items = []
        for pk, track_acronym in list(settings.items()):
            new_items.append(models.ConfigItem(technique_id=pk, config=config, track=tracks[track_acronym]))
        models.ConfigItem.objects.bulk_create(new_items)
        msg = "Configuration created. {} techniques added.".format(len(new_items))
        messages.success(
            self.request, msg
        )
        ActivityLog.objects.log(
            self.request, config, kind=ActivityLog.TYPES.modify, description=msg
        )
        return JsonResponse({"url": ""})


class DeleteConfig(RolePermsViewMixin, ConfirmDetailView):
    model = models.FacilityConfig
    template_name = "forms/delete.html"
    allowed_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        config = self.get_object()
        return (super().check_allowed() or config.facility.is_admin(self.request.user))

    def confirmed(self, *args, **kwargs):
        self.object = self.get_object()
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.delete, description='Configuration deleted'
        )
        self.object.delete()
        return JsonResponse({"url": ""})


class FacilityOptions(RolePermsViewMixin, View):
    def get(self, *args, **kwargs):
        cycle = None
        if self.request.GET.get('cycle'):
            cycle = models.ReviewCycle.objects.filter(pk=self.request.GET.get('cycle')).first()
        technique_matrix = utils.get_techniques_matrix(cycle)
        return JsonResponse(technique_matrix)


class CycleInfo(RolePermsViewMixin, detail.DetailView):
    template_name = 'proposals/fields/cycleinfo.html'
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


class EditReviewCycle(SuccessMessageMixin, RolePermsViewMixin, edit.UpdateView):
    form_class = forms.ReviewCycleForm
    template_name = "forms/modal.html"
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


class EditReviewTrack(RolePermsViewMixin, edit.UpdateView):
    form_class = forms.ReviewTrackForm
    template_name = "forms/modal.html"
    model = models.ReviewTrack
    allowed_roles = USO_ADMIN_ROLES

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        track = self.get_object()
        initial.update(committee=track.committee.all())
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        committee = data.pop('committee')
        obj = self.get_object()
        models.ReviewTrack.objects.filter(pk=obj.pk).update(**data)
        obj.committee.clear()
        obj.committee.add(*committee)
        return JsonResponse(
            {
                "url": ""
            }
        )


class SubmissionList(RolePermsViewMixin, ItemListView):
    model = models.Submission
    template_name = "item-list.html"
    list_columns = ['title', 'code', 'spokesperson', 'cycle', 'kind', 'facilities', 'state']
    list_filters = ['created', 'state', 'track', 'kind', 'cycle']
    list_search = ['proposal__title', 'proposal__id', 'proposal__spokesperson__last_name', 'proposal__keywords']
    link_url = "submission-detail"
    order_by = ['-cycle_id']
    list_title = 'Submissions'
    list_transforms = {'facilities': _fmt_beamlines, 'title': utils.truncated_title}
    list_styles = {'title': 'col-xs-2'}
    admin_roles = USO_ADMIN_ROLES
    paginate_by = 25

    def get_queryset(self, *args, **kwargs):
        qset = super().get_queryset(*args, **kwargs)
        if not self.check_admin():
            qset = qset.filter(reviewer=self.request.user)
        return qset


class BeamlineSubmissionList(RolePermsViewMixin, ItemListView):
    model = models.Submission
    template_name = "item-list.html"
    list_columns = ['code', 'title', 'spokesperson', 'cycle', 'kind', 'facilities', 'state']
    list_filters = ['created', 'state', 'track', 'kind', 'cycle']
    list_search = ['proposal__title', 'proposal__id', 'proposal__spokesperson__last_name', 'proposal__keywords']
    link_url = "submission-detail"
    order_by = ['-cycle_id']
    list_title = 'Proposal Submissions'
    list_transforms = {
        'facilities': _fmt_beamlines,
        'title': utils.truncated_title,
        'proposal__spokesperson': utils.user_format

    }

    list_styles = {'title': 'col-xs-2'}
    admin_roles = USO_ADMIN_ROLES
    allowed_roles = USO_ADMIN_ROLES

    def get_list_title(self):
        return '{} Submissions'.format(self.facility.acronym)

    def check_allowed(self):
        from beamlines.models import Facility
        self.facility = Facility.objects.get(pk=self.kwargs['pk'])
        allowed = (super().check_allowed() or self.facility.is_staff(self.request.user))
        return allowed

    def get_queryset(self, *args, **kwargs):
        self.queryset = models.Submission.objects.filter(
            techniques__config__facility=self.kwargs['pk']
        ).order_by().distinct()
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
    list_filters = ['created', 'track', 'kind', 'techniques__config__facility']
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
        columns = ['proposal', 'code', 'facilities', 'reviewer']
        for rev_type in ReviewType.objects.scored():
            columns.extend([f'{rev_type.code}_avg', f'{rev_type.code}_std'])
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
        qset = super().get_queryset(*args, **kwargs)
        qset = qset.filter(cycle_id=self.kwargs['cycle'], track__acronym=self.kwargs['track']).with_scores()
        return qset


class SubmissionDetail(RolePermsViewMixin, detail.DetailView):
    template_name = "proposals/submission_detail.html"
    model = models.Submission
    allowed_roles = USO_ADMIN_ROLES
    admin_roles = USO_ADMIN_ROLES

    def check_owner(self, obj):
        return (
                self.request.user.username in [
            obj.proposal.spokesperson.username, obj.proposal.delegate_username, obj.proposal.leader_username
        ]
        )

    def get_queryset(self):
        return self.model.objects.with_scores()

    def check_admin(self):
        submission = self.get_object()
        return super().check_admin() or any(fac.is_admin(self.request.user) for fac in submission.facilities())

    def check_allowed(self):
        submission = self.get_object()
        return (super().check_allowed() or self.check_admin() or self.check_owner(
            submission
        ) or submission.reviews.filter(
            reviewer=self.request.user, reviewer__reviewer__committee=submission.track
        ).exists())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cycle = self.object.cycle
        queryset = models.Submission.objects.filter(
            project__start_date__lte=cycle.start_date, project__end_date__gt=cycle.start_date
        ).with_scores()

        object_scores = {
            rev_type.code: getattr(self.object, f"{rev_type.code}_avg")
            for rev_type in ReviewType.objects.scored()
            if getattr(self.object, f"{rev_type.code}_avg") is not None
        }
        all_scores = {
            code: queryset.exclude(
                **{f"{code}_avg__isnull": True}
            ).values_list(f"{code}_avg", flat=True)
            for code, score in object_scores.items() if score is not None
        }
        facility_scores = {
            fac: {
                code: queryset.filter(techniques__config__facility=fac).exclude(
                    **{f"{code}_avg__isnull": True}
                ).values_list(f"{code}_avg", flat=True)
                for code, score in object_scores.items() if score is not None
            }
            for fac in self.object.facilities()
        }
        context['ranks'] = {
            rev_type: {
                'score': object_scores[rev_type.code],
                'rank': int(
                    100 - scipy_stats.percentileofscore(all_scores[rev_type.code], object_scores[rev_type.code])
                ),
                'values': list(all_scores[rev_type.code])
            }
            for rev_type in ReviewType.objects.scored()
            if rev_type.code in object_scores and all_scores.get(rev_type.code)
        }

        context['facility_ranks'] = {
            fac: {
                rev_type: {
                    'facility': fac,
                    'type': rev_type,
                    'rank': int(
                        100 - scipy_stats.percentileofscore(fac_scores[rev_type.code], object_scores[rev_type.code])
                    ),
                    'values': list(fac_scores[rev_type.code])
                }
                for rev_type in ReviewType.objects.scored()
                if rev_type.code in object_scores and fac_scores.get(rev_type.code)
            }
            for fac, fac_scores in facility_scores.items()
        }

        return context


class ReviewerList(RolePermsViewMixin, ItemListView):
    template_name = "item-list.html"
    model = models.Reviewer
    paginate_by = 25
    list_filters = ['modified', 'user__classification']
    list_columns = ['user', 'institution', 'technique_names', 'area_names']
    list_search = ['user__first_name', 'user__last_name', 'user__email']
    link_url = 'edit-reviewer-profile'
    ordering = ['-created']
    allowed_roles = USO_ADMIN_ROLES


class AddReviewCycles(RolePermsViewMixin, ConfirmDetailView):
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


class AssignReviewers(RolePermsViewMixin, ConfirmDetailView):
    template_name = "proposals/forms/assign.html"
    model = models.ReviewCycle
    allowed_roles = USO_ADMIN_ROLES

    def get_success_url(self):
        cycle = self.get_object()
        track = models.ReviewTrack.objects.get(pk=self.kwargs.get('track'))
        return reverse('assigned-reviewers', kwargs={'cycle': cycle.pk, 'track': track.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cycle = models.ReviewCycle.objects.get(pk=self.kwargs.get('pk'))
        track = models.ReviewTrack.objects.get(pk=self.kwargs.get('track'))
        context['cycle'] = cycle
        context['track'] = track
        return context

    def confirmed(self, *args, **kwargs):
        cycle = models.ReviewCycle.objects.filter(state=models.ReviewCycle.STATES.assign).get(pk=self.kwargs.get('pk'))
        track = models.ReviewTrack.objects.get(pk=self.kwargs.get('track'))

        # assign reviewers and prc members
        assignment, success = utils.assign_reviewers(cycle, track)

        if success:
            # remove all currently assigned pending scientific reviews
            to_delete = track.submissions.filter(cycle=cycle).filter(
                reviews__state=models.Review.STATES.pending, reviews__type__code__in=USO_SCIENCE_REVIEWS
            ).distinct().values_list('reviews', flat=True)
            models.Review.objects.filter(pk__in=to_delete).delete()

            review_types = ReviewType.objects.scientific()
            to_create = []
            for review_type in review_types:
                for submission, reviewers in assignment.items():
                    to_create.extend(
                        [
                            models.Review(
                                reviewer=u.user, reference=submission, type=review_type, cycle=submission.cycle,
                                form_type=review_type.form_type, due_date=cycle.due_date
                            ) for u in reviewers
                        ]
                    )
                break  # only one type of review for now
            messages.success(self.request, 'Reviewer assignment successful')
            models.Review.objects.bulk_create(to_create)
            ActivityLog.objects.log(
                self.request, track, kind=ActivityLog.TYPES.task, description='Reviewers Assigned'
            )
        else:
            messages.error(self.request, 'No feasible reviewer assignment was found')
        return JsonResponse({"url": self.get_success_url()})


class ReviewCompatibility(RolePermsViewMixin, detail.DetailView):
    model = models.Review
    template_name = "proposals/review_compat.html"
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
    paginate_by = 10
    list_columns = ['proposal', 'cycle', 'track', 'state']
    list_filters = ['created', 'state', 'track', 'cycle']
    list_search = ['proposal__title', 'proposal__id', 'proposal__team', 'proposal__keywords',
                   'proposal__spokesperson__last_name']
    link_url = "submission-detail"
    list_styles = {'proposal': 'col-xs-6'}
    order_by = ['-cycle__start_date', '-created']
    list_title = 'Reviewer Assignments'
    allowed_roles = USO_ADMIN_ROLES

    def get_queryset(self, *args, **kwargs):
        track = models.ReviewTrack.objects.get(pk=self.kwargs['track'])
        cycle = models.ReviewCycle.objects.get(pk=self.kwargs['cycle'])
        self.queryset = cycle.submissions.filter(track=track).all()
        return super().get_queryset(*args, **kwargs)


class ReviewerAssignments(RolePermsViewMixin, ItemListView):
    model = models.Submission
    template_name = "proposals/assignment-list.html"
    paginate_by = 20
    list_columns = ['proposal', 'cycle', 'track', 'state']
    list_filters = ['created', 'state', 'track', 'cycle']
    list_search = ['proposal__title', 'proposal__id', 'proposal__team', 'proposal__keywords',
                   'proposal__spokesperson__last_name']
    link_url = "submission-detail"
    list_styles = {'proposal': 'col-xs-6'}
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

    def get_list_title(self):
        return '{} ~ {}'.format(self.reviewer.user, self.cycle)


class PRCAssignments(RolePermsViewMixin, ItemListView):
    model = models.Submission
    template_name = "proposals/assignment-list.html"
    paginate_by = 20
    list_columns = ['proposal', 'cycle', 'track', 'state']
    list_filters = ['created', 'state', 'track', 'cycle']
    list_search = ['proposal__title', 'proposal__id', 'proposal__team', 'proposal__keywords',
                   'proposal__spokesperson__last_name']
    link_url = "submission-detail"
    list_styles = {'proposal': 'col-xs-6'}
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
        self.reviewer = models.Reviewer.objects.get(pk=self.request.user.reviewer.pk)
        self.cycle = models.ReviewCycle.objects.next()
        self.queryset = self.reviewer.committee_proposals(self.cycle)
        return super().get_queryset(*args, **kwargs)


class ReviewerOptOut(RolePermsViewMixin, edit.FormView):
    form_class = forms.OptOutForm
    template_name = "forms/modal.html"
    success_url = reverse_lazy("user-dashboard")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_initial(self):
        self.initial = super().get_initial()
        self.initial.update({"cycle": models.ReviewCycle.objects.get(pk=self.kwargs['pk'])})
        return self.initial

    def form_valid(self, form):
        data = form.cleaned_data
        reviewer = self.request.user.reviewer
        messages.success(self.request, 'You have successfully opted out of the next round of reviews.')
        comments = [
            _f for _f in [reviewer.comments, f"Opted out of cycle {data['cycle']} {data['reason']}"]
            if _f
        ]
        reviewer.comments = "; ".join(comments)
        reviewer.save()
        data['cycle'].reviewers.remove(reviewer)
        ActivityLog.objects.log(
            self.request, reviewer, kind=ActivityLog.TYPES.task,
            description='Reviewer opted out: {}'.format(data['reason'])
        )
        return JsonResponse({"url": ""})


class AddReviewAssignment(RolePermsViewMixin, edit.UpdateView):
    form_class = forms.ReviewerAssignmentForm
    model = models.Submission
    template_name = "forms/modal.html"
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
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        if data['reviewers'].filter(committee__isnull=False).exists():
            self.object.reviews.filter(reviewer__reviewer__committee__isnull=False).delete()
            messages.success(self.request, "Committee members were swapped.")

        review_type = ReviewType.objects.scientific().first()
        if review_type:
            to_add = [
                models.Review(
                    reviewer=rev.user, cycle=self.object.cycle, reference=self.object,
                    due_date=self.object.cycle.due_date,
                    type=review_type, state=models.Review.STATES.pending, form_type=review_type.form_type
                ) for rev in data['reviewers']
            ]
            models.Review.objects.bulk_create(to_add)
            messages.success(self.request, "Reviews were added")
            ActivityLog.objects.log(
                self.request, self.object, kind=ActivityLog.TYPES.modify, description='Reviewers added'
            )
        return JsonResponse({"url": ""})


class DeleteReview(RolePermsViewMixin, ConfirmDetailView):
    model = models.Review
    template_name = "proposals/forms/delete-review.html"
    allowed_roles = USO_ADMIN_ROLES

    def check_allowed(self):
        allowed = super().check_allowed()
        if not allowed:
            review = self.get_object()
            if hasattr(self.request.user, 'reviewer'):
                reviewer = self.request.user.reviewer
                allowed = (
                        reviewer and reviewer.active and reviewer.committee == review.reference.track
                        and review.reference.reviews.filter(reviewer=reviewer.user).scientific().exists()
                )
        return allowed

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.model.objects.filter(state=self.model.STATES.pending)
        return super().get_queryset(*args, **kwargs)

    def confirmed(self, *args, **kwargs):
        obj = self.get_object()
        if obj.reviewer != self.request.user:
            obj.delete()
        else:
            messages.warning(self.request, "You can't remove your own review")
        return JsonResponse({"url": ""})


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


class AddReviewerList(RolePermsViewMixin, ItemListView):
    model = models.Reviewer
    allowed_roles = USO_ADMIN_ROLES
    template_name = "proposals/add-cycle-reviewers.html"
    paginate_by = 60
    list_filters = ['modified', 'user__classification', 'cycles']
    list_columns = ['user', 'user__institution__name', 'technique_names', 'committee']
    list_search = [
        'user__first_name', 'user__last_name', 'user__email', 'techniques__name', 'areas__name',
        'techniques__acronym'
    ]
    order_by = ['user__last_name']
    ordering_proxies = {'user': 'user__last_name'}
    list_transforms = {'techniques': _name_list, 'areas': _name_list}

    list_title = 'Add/Remove Reviewers'

    def get_link_url(self, obj):
        cycle = self.kwargs.get('cycle')
        if obj.pk in self.selected:
            return reverse_lazy(
                'del-cycle-reviewer', kwargs={self.link_kwarg: getattr(obj, self.link_kwarg), 'cycle': cycle}
            )
        else:
            return reverse_lazy(
                'change-cycle-reviewers', kwargs={self.link_kwarg: getattr(obj, self.link_kwarg)}
            )

    def get_grid_template(self, obj):
        if obj.pk in self.selected:
            return "proposals/del-reviewer-grid.html"
        else:
            return "proposals/add-reviewer-grid.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cycle'] = self.cycle
        context['cycle_reviewers'] = self.selected
        return context

    def get_queryset(self, *args, **kwargs):
        self.cycle = models.ReviewCycle.objects.filter(pk=self.kwargs['pk']).first()
        self.queryset = models.Reviewer.objects.filter(active=True)
        self.selected = self.cycle.reviewers.values_list('pk', flat=True)
        return super().get_queryset(*args, **kwargs)


class AddReviewerAPI(RolePermsViewMixin, View):
    allowed_roles = USO_ADMIN_ROLES

    def get(self, *args, **kwargs):
        reviewer = models.Reviewer.objects.filter(pk=self.kwargs['pk']).first()
        cycle = models.ReviewCycle.objects.filter(pk=self.kwargs['cycle']).first()
        if reviewer and cycle:
            cycle.reviewers.add(reviewer)
            messages.add_message(
                self.request, messages.SUCCESS, "Reviewer {} added to cycle {}.".format(reviewer, cycle)
            )
        self.success_url = reverse_lazy('change-cycle-reviewers', kwargs={'pk': cycle.pk})
        return HttpResponseRedirect(self.success_url)


class RemoveReviewerAPI(RolePermsViewMixin, View):
    allowed_roles = USO_ADMIN_ROLES

    def get(self, *args, **kwargs):
        cycle = models.ReviewCycle.objects.filter(pk=self.kwargs['cycle']).first()
        if cycle:
            cycle.reviewers.remove(self.kwargs['pk'])
            messages.add_message(
                self.request, messages.SUCCESS, "Reviewer removed from cycle {}.".format(cycle)
            )
        self.success_url = reverse_lazy('change-cycle-reviewers', kwargs={'pk': cycle.pk})
        return HttpResponseRedirect(self.success_url)


class StartReviews(RolePermsViewMixin, ConfirmDetailView):
    queryset = models.ReviewCycle.objects.filter(state=models.ReviewCycle.STATES.assign)
    template_name = "proposals/forms/reviews.html"
    model = models.ReviewCycle
    allowed_roles = USO_ADMIN_ROLES

    def confirmed(self, *args, **kwargs):
        cycle = self.get_object()
        if cycle:
            info = defaultdict(list)
            reviews = models.Review.objects.none()

            # gather relevant scientific reviews
            reviews |= models.Review.objects.filter(cycle=cycle, state=models.Review.STATES.pending).scientific()

            # gather all reviews for each reviewer
            for rev in reviews.all():
                if rev.reviewer:
                    info[rev.reviewer].append(rev)
                else:
                    info[rev.role].append(rev)

            # generate notifications
            for recipient, revs in list(info.items()):
                notify.send(
                    [recipient], 'review-request', level=notify.LEVELS.important, context={
                        'reviews': revs,
                    }
                )
                models.Review.objects.filter(pk__in=[r.pk for r in revs]).update(state=models.Review.STATES.open)

            models.ReviewCycle.objects.filter(pk=cycle.pk).update(state=models.ReviewCycle.STATES.review)
            ActivityLog.objects.log(
                self.request, cycle, kind=ActivityLog.TYPES.modify, description='Scientific Reviewers Notified'
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


class AddScoreAdjustment(RolePermsViewMixin, edit.CreateView):
    form_class = forms.AdjustmentForm
    model = models.ScoreAdjustment
    template_name = "forms/modal.html"
    allowed_roles = USO_ADMIN_ROLES

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.submission = models.Submission.objects.get(pk=self.kwargs['pk'])
        kwargs['request'] = self.request
        kwargs['submission'] = self.submission
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        submission = models.Submission.objects.get(pk=self.kwargs['pk'])
        if hasattr(submission, 'adjustment'):
            initial['value'] = submission.adjustment.value
            initial['reason'] = submission.adjustment.reason
        return initial

    def form_valid(self, form):
        data = form.cleaned_data

        if self.submission.state == self.submission.STATES.reviewed:
            data['user'] = self.request.user
            obj, created = self.model.objects.update_or_create(submission=self.submission, defaults=data)
            ActivityLog.objects.log(
                self.request, self.submission, kind=ActivityLog.TYPES.task,
                description='Score Adjusted by {}'.format(data['value'])
            )
            messages.success(self.request, f'Score adjustment of {obj.value} applied to submission')
        else:
            messages.warning(self.request, 'Score adjustment not allowed for pending submissions')
        return JsonResponse({"url": ""})


class DeleteAdjustment(RolePermsViewMixin, ConfirmDetailView):
    model = models.ScoreAdjustment
    template_name = "forms/delete.html"
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


class UpdateReviewComments(RolePermsViewMixin, edit.UpdateView):
    form_class = forms.ReviewCommentsForm
    queryset = models.Submission.objects.filter(state=models.Submission.STATES.reviewed)
    template_name = "forms/modal.html"
    allowed_roles = USO_ADMIN_ROLES

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

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
