import functools
import json
import math
import operator
from datetime import date

from crisp_modals.views import ModalDeleteView
from django.conf import settings
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.views.generic import TemplateView, View
from django.views.generic.edit import UpdateView
from formtools.wizard.views import SessionWizardView
from itemlist.views import ItemListView

from beamlines.filters import BeamlineFilterFactory
from misc.filters import DateLimitFilterFactory, DateLimit
from misc.models import ActivityLog
from roleperms.views import RolePermsViewMixin
from . import models, forms, stats

USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ['admin:uso'])
USO_STAFF_ROLES = getattr(settings, "USO_STAFF_ROLES", ['staff', 'employee'])
USO_CURATOR_ROLES = getattr(settings, "USO_CURATOR_ROLES", ['curator:publications'])


# Create your views here.
FromYearListFilter = DateLimitFilterFactory.new(
    models.Publication, field_name='date', filter_title='From Year', limit=DateLimit.LEFT
)
ToYearListFilter = DateLimitFilterFactory.new(
    models.Publication, field_name='date', filter_title='To Year', limit=DateLimit.RIGHT
)


def _format_beamlines(bls, obj=None):
    return ', '.join([bl.acronym for bl in bls.all()])


def _format_areas(areas, obj=None):
    return ', '.join([area.name for area in areas.all()])


def _fmt_citations(citation, obj=None):
    return mark_safe(citation)


class PublicationList(RolePermsViewMixin, ItemListView):
    model = models.Publication
    template_name = "tooled-item-list.html"
    tool_template = "publications/publication-tools.html"
    paginate_by = 25
    list_filters = ['kind', 'tags', BeamlineFilterFactory.new("beamlines"), FromYearListFilter, ToYearListFilter]
    list_title = "All Publications"
    list_columns = ['cite', 'facility_codes', 'kind']
    list_transforms = {'cite': _fmt_citations, 'areas': _format_areas}
    list_search = ['authors', 'title', 'keywords']
    ordering = ['-year', 'kind', 'authors']
    admin_roles = USO_CURATOR_ROLES + USO_ADMIN_ROLES

    def get_queryset(self, *args, **kwargs):
        queryset = self.model.objects.filter(reviewed=True)
        acronym = self.kwargs.get('beamline')
        year = self.kwargs.get('year')
        end_year = self.kwargs.get('end_year')
        filters = Q()
        if acronym:
            filters &= Q(beamlines__parent__acronym__iexact=acronym) | Q(beamlines__acronym__iexact=acronym)
            self.list_title = f"{acronym} Publications"
        if end_year:
            filters &= Q(date__year__gte=year, date__year__lte=end_year)
        elif year:
            filters &= Q(date__year=year)
        self.queryset = queryset.filter(filters)
        return super().get_queryset(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['admin'] = self.request.user.has_any_role(*self.admin_roles)
        else:
            context['admin'] = False
        return context


class PublicationAdminList(SuccessMessageMixin, ItemListView):
    model = models.Publication
    template_name = "tooled-item-list.html"
    tool_template = "publications/publication-tools.html"
    allowed_roles = USO_ADMIN_ROLES + USO_CURATOR_ROLES
    admin_roles = USO_CURATOR_ROLES + USO_ADMIN_ROLES
    list_title = 'Modify Publications'
    paginate_by = 25
    list_filters = ['kind', 'tags', BeamlineFilterFactory.new("beamlines"), FromYearListFilter, ToYearListFilter]
    list_columns = ['title', 'kind', 'code', 'facility_codes', 'date', 'reviewed']
    list_transforms = {'cite': _fmt_citations}
    link_url = 'review-publication'


class PublicationReviewList(PublicationAdminList):
    list_title = 'Pending Publications'
    model = models.Publication
    paginate_by = 50
    list_columns = ['title', 'kind', 'code', 'facility_codes', 'created']
    list_transforms = {'cite': _fmt_citations, 'areas': _format_areas}
    list_search = ['authors', 'title', 'keywords']
    ordering = ['-year', 'kind', 'authors']

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.model.objects.filter(reviewed=False).order_by('-year', 'kind', 'authors')
        return super().get_queryset(*args, **kwargs)


class UserPublicationList(RolePermsViewMixin, ItemListView):
    template_name= "tooled-item-list.html"
    tool_template = "publications/publication-tools.html"
    paginate_by = 15
    list_filters = ['kind', 'tags', BeamlineFilterFactory.new("beamlines"), FromYearListFilter, ToYearListFilter]
    list_columns = ['cite', 'facility_codes', 'kind']
    list_transforms = {'cite': _fmt_citations, 'beamlines': _format_beamlines}
    list_search = ['authors', 'title', 'date', 'keywords']
    ordering = ['kind', '-year', 'authors']
    list_title = 'My Publications'

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.request.user.publications.all()
        return super().get_queryset(*args, **kwargs)


def get_author_names(user):
    if hasattr(user, 'get_name_variants'):
        return user.get_name_variants()
    else:
        return [user.get_full_name()]


def get_author_matches(user):
    names = get_author_names(user)
    query = functools.reduce(operator.or_, [Q(authors__icontains=name) for name in names], Q())

    return models.Publication.objects.exclude(
        users__id__exact=user.pk
    ).filter(query).count()


def _claim_link(claimed, obj):
    if claimed:
        url = reverse_lazy("unclaim-publication", kwargs={"pk": obj.pk})
        return mark_safe(
            f'<a href="{url}" class="btn btn-xs btn-danger" title="Add"><i class="bi bi-x-lg"></i></a>'
        )
    else:
        url = reverse_lazy("claim-publication", kwargs={"pk": obj.pk})
        return mark_safe(
            f'<a href="{url}" class="btn btn-xs btn-success" title="Remove"><i class="bi bi-plus-lg"></i></a>'
        )


class ClaimPublicationList(RolePermsViewMixin, ItemListView):
    model = models.Publication
    template_name = "tooled-item-list.html"
    paginate_by = 15
    list_filters = ['kind', 'tags', BeamlineFilterFactory.new("beamlines"), FromYearListFilter, ToYearListFilter]
    list_columns = ['cite', 'date', 'claimed']
    list_transforms = {
        'cite': _fmt_citations,
        'claimed': _claim_link
    }
    list_search = ['authors', 'title', 'date']
    ordering = ['kind', '-year', 'authors']
    list_styles = {
        'date': 'text-nowrap',
        'claimed': 'col-auto text-center'
    }
    list_title = 'Matched/Claimed Publications'

    def get_queryset(self, *args, **kwargs):
        user = self.request.user
        names = get_author_names(user)
        query = functools.reduce(operator.__or__, [Q(authors__icontains=name) for name in names], Q())

        self.queryset = models.Publication.objects.annotate(
            claimed=Q(users__id__exact=user.pk)
        ).filter(query | Q(users=user)).all().order_by('claimed')
        return super().get_queryset(*args, **kwargs)


class ClaimPublication(RolePermsViewMixin, View):
    success_url = reverse_lazy('claim-publication-list')

    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            q = models.Publication.objects.filter(pk=self.kwargs['pk'])
            if q.count():
                obj = q[0]
                obj.users.add(self.request.user)
                obj.save()
                messages.add_message(self.request, messages.SUCCESS, "Publication has been added to your list.")
            else:
                messages.add_message(self.request, messages.ERROR, "Publication not found.")
        return HttpResponseRedirect(self.success_url)


class UnclaimPublication(RolePermsViewMixin, View):
    success_url = reverse_lazy('claim-publication-list')

    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            q = self.request.user.publications.filter(pk=self.kwargs['pk'])
            if q.count():
                obj = q[0]
                obj.users.remove(self.request.user)
                obj.save()
                messages.add_message(self.request, messages.SUCCESS, "Publication has been removed from your list.")
            else:
                messages.add_message(self.request, messages.ERROR, "Publication not found.")
        return HttpResponseRedirect(self.success_url)


class ActivitySummary(RolePermsViewMixin, TemplateView):
    admin_roles = USO_CURATOR_ROLES + USO_ADMIN_ROLES
    allowed_roles = USO_STAFF_ROLES + USO_ADMIN_ROLES
    template_name = "publications/activity-summary.html"


class QualitySummary(RolePermsViewMixin, TemplateView):
    admin_roles = USO_CURATOR_ROLES + USO_ADMIN_ROLES
    allowed_roles = USO_STAFF_ROLES + USO_ADMIN_ROLES
    template_name = "publications/quality-summary.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.facility = None
        acronym = self.kwargs.get('beamline')
        if acronym:
            self.facility = models.Facility.objects.filter(acronym__iexact=acronym).first()
            if self.facility:
                context['beamline'] = self.facility
                context['beamline_activity'] = {
                    'qset': models.Publication.objects.filter(
                        Q(beamlines__parent__acronym__iexact=acronym) | Q(beamlines__acronym__iexact=acronym)
                    ).distinct(), 'name': self.facility.name, 'description': self.facility.description
                }
            else:
                context['beamline'] = None

        return context


class FundingSummary(RolePermsViewMixin, TemplateView):
    admin_roles = USO_CURATOR_ROLES
    allowed_roles = USO_STAFF_ROLES
    template_name = "publications/funding-summary.html"


class KeywordCloud(RolePermsViewMixin, TemplateView):
    admin_roles = USO_CURATOR_ROLES
    template_name = "publications/keyword-report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['words'] = stats.get_keywords(models.Article.objects, transform=math.sqrt)
        if self.request.user.is_authenticated:
            context['admin'] = self.request.user.has_any_role(*self.admin_roles)
        else:
            context['admin'] = False
        return context


class PublicationReview(SuccessMessageMixin, RolePermsViewMixin, UpdateView):
    admin_roles = USO_CURATOR_ROLES
    allowed_roles = USO_CURATOR_ROLES + USO_ADMIN_ROLES
    template_name = "publications/forms/review_form.html"
    model = models.Publication
    success_url = reverse_lazy('publication-review-list')
    success_message = "Publication has been updated and marked as reviewed."

    def get_object(self, *args, **kwargs):
        objects = models.Publication.objects.filter(pk=self.kwargs.get('pk')).all()
        if objects:
            return objects[0]
        else:
            raise models.Publication.DoesNotExist

    def get_form_class(self):
        key = self.object.kind

        return {
            'article': forms.ArticleReviewForm,
            'proceeding': forms.ArticleReviewForm,
            'phd_thesis': forms.BookReviewForm,
            'msc_thesis': forms.BookReviewForm,
            'magazine': forms.ArticleReviewForm,
            'chapter': forms.BookReviewForm,
            'book': forms.BookReviewForm,
        }.get(key, forms.PublicationReviewForm)

    def form_valid(self, form):
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.task, description='Publication marked as reviewed'
        )
        return super().form_valid(form)


class PublicationDelete(RolePermsViewMixin, ModalDeleteView):
    admin_roles = USO_ADMIN_ROLES + USO_CURATOR_ROLES
    allowed_roles = USO_ADMIN_ROLES + USO_CURATOR_ROLES
    queryset = models.Publication.objects.all()
    success_url = reverse_lazy('publication-review-list')

    def confirmed(self, request, *args, **kwargs):
        self.object = self.get_object()
        msg = 'Publication deleted'
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.delete, description=msg
        )
        messages.success(self.request, msg)
        return super().confirmed(request, *args, **kwargs)


class PublicationWizard(SessionWizardView):
    form_list = [('0', forms.PubWizardForm1), ('1', forms.PubWizardForm2), ('2', forms.PubWizardForm3)]
    template_name = "publications/forms/submit-form.html"

    def get_success_url(self):
        if self.request.user.is_authenticated:
            success_url = reverse_lazy('publication-list')
        else:
            success_url = reverse_lazy('ext-publication-list')
        return success_url

    def done(self, form_list, **kwargs):
        """
        Create the new publication here, based on the cleaned_data from the forms
        """
        data = form_list[-1].cleaned_data
        details = json.loads(data['details'])
        info = details
        info.update(notes=data.get('notes'))

        if details.get('journal'):
            journal = details['journal']
            if isinstance(journal, int):
                j = models.Journal.objects.get(pk=journal)
            else:
                issn = journal.pop('issn', '').strip()
                j, created = models.Journal.objects.get_or_create(issn=issn, defaults=journal)
            info.update(journal=j)

        obj = data.get('obj', None)
        funders = details.pop('funders', [])
        if not obj:
            obj = models.Publication.objects.create(**info)
            ActivityLog.objects.log(
                self.request, obj, kind=ActivityLog.TYPES.create,
                description=f'Publication Added by {self.request.user}'
            )
        else:
            models.Publication.objects.filter(pk=obj.pk).update(**info)
            ActivityLog.objects.log(
                self.request, obj, kind=ActivityLog.TYPES.create,
                description=f'Publication Re-entered by {self.request.user}'
            )

        if data.get('beamlines'):
            items = {bl for bl in data['beamlines'] if not bl.kind == bl.Types.sector}
            for bl in [x for x in data['beamlines'] if (x.kind == x.Types.sector)]:
                items.update(bl.children.all())
            obj.beamlines.add(*items)

        if data.get('funders'):
            known_funders = data['funders']
            obj.funders.add(*known_funders)
            new_funders = []
            for funder in funders:
                doi = funder.pop('doi', None)
                if not doi:
                    continue
                f, created = models.FundingSource.objects.get_or_create(doi=doi, defaults=funder)
                new_funders.append(f)
            obj.funders.add(*new_funders)

        if data.get('author'):
            if self.request.user.is_authenticated:
                obj.users.add(self.request.user)
        messages.add_message(self.request, messages.SUCCESS, "Successfully added publication.")
        return HttpResponseRedirect(self.get_success_url())

    def get_form(self, step=None, data=None, files=None):
        if data:
            if data.get('submit') != 'Submit':
                step = data.get('submit')
                self.storage.current_step = step
                data = None

        form = super().get_form(step, data, files)
        if self.steps.next == step:
            form_info = {}
            if step == "1" or self.form_list['1'] == form.__class__:
                cleaned_data = self.get_cleaned_data_for_step(self.steps.first) or {}
                if cleaned_data['details']:
                    details = json.loads(cleaned_data['details'])
                    form_info['details'] = json.dumps(details)

            elif step == "2" or self.form_list['2'] == form.__class__:
                cleaned_data = self.get_cleaned_data_for_step('1') or {}
                try:
                    details = json.loads(cleaned_data.get('details', '{}'))
                except json.JSONDecodeError:
                    details = {}
                kind = details.get('kind', cleaned_data.get('kind', None))

                details.update(
                    {f: cleaned_data[f] for f in list(cleaned_data.keys()) if
                     f != 'details' and not details.get(f, None)}
                )

                matches = models.check_unique(
                    details.get('title', None), details.get('authors', None), details.get('code', None)
                )
                if isinstance(details['date'], date):
                    details['date'] = details['date'].isoformat()

                form_info = {
                    'details': json.dumps(details),
                    'kind': kind,
                    'obj': matches and matches[0] or None
                }

                funders = []
                for f in details.get('funders', []):
                    fs = models.FundingSource.objects.filter(doi__iexact=f['doi']).first()
                    if fs:
                        funders.append(fs)
                form_info['funders'] = funders

            if form_info:
                form.initial = form_info
            form.update_helper()

        return form


def abbrev_author(name):
    parts = [x.strip() for x in name.strip().split(',')]
    if len(parts) > 1:
        return f"{parts[0].upper()}, {'' if not parts[1] else parts[1][0].upper()}"
    else:
        return name.strip().upper()


class InstitutionMetrics(RolePermsViewMixin, TemplateView):
    admin_roles = USO_CURATOR_ROLES + USO_ADMIN_ROLES
    allowed_roles = USO_STAFF_ROLES
    template_name = "publications/institution-metrics.html"

    def get_context_data(self, **kwargs):
        from users.models import Institution
        context = super().get_context_data(**kwargs)

        institution = Institution.objects.get(pk=self.kwargs.get('pk'))
        context['institution'] = institution
        authors = {f"{u.last_name.upper()}, {u.first_name[0]}" for u in institution.users.all()}
        pks = set()
        for p in models.Publication.objects.all():
            pub_authors = {abbrev_author(x) for x in p.authors.upper().split(';') if x}
            if (pub_authors & authors):
                pks.add(p.pk)
        queryset = models.Publication.objects.filter(pk__in=pks)
        articles = models.Article.objects.filter(pk__in=pks)
        context['metrics'] = stats.get_metrics(articles, True)
        context['queryset'] = queryset
        context['pub_info'] = stats.get_publist(queryset)
        return context
