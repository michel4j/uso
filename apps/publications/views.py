import functools
import json
import math
import operator

from django.contrib import messages
from django.contrib.admin.utils import NestedObjects
from django.contrib.messages.views import SuccessMessageMixin
from django.db import DEFAULT_DB_ALIAS
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from django.views.generic import TemplateView, View
from django.views.generic.edit import UpdateView, DeleteView
from formtools.wizard.views import SessionWizardView
from itemlist.views import ItemListView

from beamlines.filters import BeamlineFilterFactory
from misc.filters import DateLimitFilterFactory, DateLimit
from misc.models import ActivityLog
from roleperms.views import RolePermsViewMixin
from . import models, forms, stats

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
    queryset = models.Publication.objects.all().select_subclasses()
    template_name = "publications/publication-list.html"
    paginate_by = 15
    list_filters = ['kind', 'tags', BeamlineFilterFactory.new("beamlines"), FromYearListFilter, ToYearListFilter]
    list_title = "All Publications"
    list_columns = ['cite', 'facility_codes', 'kind']
    list_transforms = {'cite': _fmt_citations, 'areas': _format_areas}
    list_search = ['authors', 'title', 'keywords']
    ordering = ['-year', 'kind', 'authors']
    admin_roles = ['publications-admin']

    def get_queryset(self, *args, **kwargs):
        qset = models.Publication.objects.all()
        acronym = self.kwargs.get('beamline')
        year = self.kwargs.get('year')
        end_year = self.kwargs.get('end_year')
        filters = Q(reviewed=True)
        if acronym:
            filters &= Q(beamlines__parent__acronym__iexact=acronym) | Q(beamlines__acronym__iexact=acronym)
            self.list_title = f"{acronym} Publications"
        if end_year:
            filters &= Q(date__year__gte=year, date__year__lte=end_year)
        elif year:
            filters &= Q(date__year=year)
        self.queryset = qset.filter(filters).select_subclasses()
        return super().get_queryset(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['admin'] = self.request.user.has_roles(self.admin_roles)
        else:
            context['admin'] = False
        return context


class PublicationAdminList(SuccessMessageMixin, PublicationList):
    template_name = "publications/publication-list.html"
    allowed_roles = ['publications-admin', 'administrator:uso']
    admin_roles = ['publications-admin']
    list_title = 'Modify Publications'
    list_columns = ['title', 'kind', 'code', 'facility_codes', 'date', 'reviewed']
    list_transforms = {'cite': _fmt_citations}
    link_url = 'review-publication'
    paginate_by = 50


class PublicationReviewList(PublicationAdminList):
    template_name = "publications/publication-list.html"
    list_columns = ['title', 'kind', 'code', 'facility_codes', 'date', 'reviewed']
    list_title = 'Pending Publications'
    order_by = ['-created', 'authors']

    def get_queryset(self, *args, **kwargs):
        queryset = super().get_queryset(*args, **kwargs)
        return queryset.filter(reviewed=False)


class UserPublicationList(RolePermsViewMixin, ItemListView):
    admin_roles = ['publications-admin']
    template_name = "publications/publication-list.html"
    paginate_by = 15
    list_filters = ['kind', 'tags', BeamlineFilterFactory.new("beamlines"), FromYearListFilter, ToYearListFilter]
    list_columns = ['cite', 'facility_codes', 'kind']
    list_transforms = {'cite': _fmt_citations, 'beamlines': _format_beamlines}
    list_search = ['authors', 'title', 'date', 'keywords']
    ordering = ['kind', '-year', 'authors']
    list_title = 'My Publications'

    def get_queryset(self, *args, **kwargs):
        self.queryset = self.request.user.publications.select_subclasses()
        return super().get_queryset(*args, **kwargs)


def get_author_names(user):
    names = {"{}, {}.".format(user.last_name, user.first_name[0]), "{}, {}".format(user.last_name, user.first_name), }
    if user.preferred_name:
        names |= {"{}, {}.".format(user.last_name, user.preferred_name[0]), "{}, {}".format(user.last_name, user.preferred_name), }
    if user.other_names:
        names |= {"{}, {}.".format(user.last_name, user.other_names[0]), "{}, {}".format(user.last_name, user.other_names),
            "{}, {}. {}.".format(user.last_name, user.other_names[0], user.first_name[0]),
            "{}, {}. {}.".format(user.last_name, user.first_name[0], user.other_names[0]), "{}, {}.".format(user.other_names, user.first_name[0]),
            "{}, {}".format(user.other_names, user.first_name), "{}, {} {}".format(user.last_name, user.first_name, user.other_names),
            "{}, {} {}".format(user.last_name, user.other_names, user.first_name), }
        if user.preferred_name:
            names |= {"{}, {}. {}.".format(user.last_name, user.other_names[0], user.preferred_name[0]),
                "{}, {}. {}.".format(user.last_name, user.preferred_name[0], user.other_names[0]),
                "{}, {}.".format(user.other_names, user.preferred_name[0]), "{}, {}".format(user.other_names, user.preferred_name),

            }
    return names


def get_author_matches(user):
    names = get_author_names(user)
    query = functools.reduce(operator.or_, [Q(authors__icontains=name) for name in names], Q())

    return models.Publication.objects.exclude(
        users__id__exact=user.pk
    ).filter(query).count()


class ClaimPublicationList(RolePermsViewMixin, ItemListView):
    model = models.Publication
    admin_roles = ['publications-admin']
    template_name = "publications/claim_publications.html"
    paginate_by = 15
    list_filters = ['kind', 'tags', BeamlineFilterFactory.new("beamlines"), FromYearListFilter, ToYearListFilter]
    list_columns = ['cite', 'kind']
    list_transforms = {'cite': _fmt_citations, 'beamlines': _format_beamlines}
    list_search = ['authors', 'title', 'date']
    ordering = ['kind', '-year', 'authors']
    list_styles = {'cite': 'col-xs-10', }
    list_title = 'Matched Publications'

    def get_queryset(self, *args, **kwargs):
        user = self.request.user
        names = get_author_names(user)
        query = functools.reduce(operator.or_, [Q(authors__icontains=name) for name in names], Q())

        self.queryset = models.Publication.objects.filter(query).select_subclasses()
        return super().get_queryset(*args, **kwargs)


class ClaimPublication(RolePermsViewMixin, View):
    success_url = reverse_lazy('claim-publication-list')

    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            q = models.Publication.objects.filter(pk=self.kwargs['pk'])
            if q.count():
                obj = q[0]
                obj.users.add(self.request.user)
                if not isinstance(obj.history, list):
                    obj.history = []
                obj.history.append('Claimed by {0} on {1}'.format(self.request.user, timezone.now().isoformat()))
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
                if not isinstance(obj.history, list):
                    obj.history = []
                obj.history.append('Unclaimed by {0} on {1}'.format(self.request.user, timezone.now().isoformat()))
                obj.save()
                messages.add_message(self.request, messages.SUCCESS, "Publication has been removed from your list.")
            else:
                messages.add_message(self.request, messages.ERROR, "Publication not found.")
        return HttpResponseRedirect(self.success_url)


class ActivitySummary(RolePermsViewMixin, TemplateView):
    admin_roles = ['publications-admin']
    allowed_roles = ['employee']
    template_name = "publications/activity-summary.html"


class QualitySummary(RolePermsViewMixin, TemplateView):
    admin_roles = ['publications-admin']
    allowed_roles = ['employee']
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
    admin_roles = ['publications-admin']
    allowed_roles = ['employee']
    template_name = "publications/funding-summary.html"


class KeywordCloud(RolePermsViewMixin, TemplateView):
    admin_roles = ['publications-admin']
    template_name = "publications/keyword-report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['words'] = stats.get_keywords(models.Article.objects, transform=math.sqrt)
        if self.request.user.is_authenticated:
            context['admin'] = self.request.user.has_roles(self.admin_roles)
        else:
            context['admin'] = False
        return context


class PublicationReview(SuccessMessageMixin, RolePermsViewMixin, UpdateView):
    admin_roles = ['publications-admin']
    allowed_roles = ['publications-admin', 'administrator:uso']
    template_name = "publications/forms/review_form.html"
    model = models.Publication
    success_url = reverse_lazy('publication-review-list')
    success_message = "Publication has been updated and marked as reviewed."

    def get_object(self):
        objects = models.Publication.objects.filter(pk=self.kwargs.get('pk')).select_subclasses()
        if objects:
            return objects[0]
        else:
            raise models.Publication.DoesNotExist

    def get_form_class(self):
        key = self.object.__class__.__name__

        return {
            'Article': forms.ArticleReviewForm, 'Book': forms.BookReviewForm, 'PDBDeposition': forms.PDBReviewForm,
        }.get(key, forms.PublicationReviewForm)

    def form_valid(self, form):
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.task, description='Publication marked as reviewed'
        )
        return super().form_valid(form)


class PublicationDelete(RolePermsViewMixin, DeleteView):
    admin_roles = ['publications-admin']
    allowed_roles = ['publications-admin']
    queryset = models.Publication.objects.select_subclasses()
    success_url = reverse_lazy('publication-review-list')
    template_name = "publications/forms/confirm_delete.html"

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
        self.object = self.get_object()
        msg = 'Publication deleted'
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.delete, description=msg
        )
        messages.success(self.request, msg)
        return super().delete(request, *args, **kwargs)


MODELS = {
    'article': models.Article, 'msc_thesis': models.Book, 'phd_thesis': models.Book, 'pdb': models.PDBDeposition, "patent": models.Patent,
    'book': models.Book
}


class PublicationWizard(SessionWizardView):
    form_list = [('0', forms.PubWizardForm1), ('1', forms.PubWizardForm2), ('2', forms.PubWizardForm3)]
    template_name = "publications/forms/publication_form.html"

    def get_success_url(self):
        if self.request.user.is_authenticated:
            success_url = reverse_lazy('publication-list')
        else:
            success_url = reverse_lazy('ext-publication-list')
        return success_url

    def done(self, form_list, **kwargs):
        """ Create the new publication here, based on the cleaned_data from the forms """
        data = form_list[-1].cleaned_data
        details = json.loads(data['details'])

        info = {}
        info.update(
            {f: details.get(f) for f in ['authors', 'title', 'date', 'keywords', 'kind', 'reviewed', 'code'] if details.get(f)}
        )
        info.update(notes=data.get('notes'))
        info.update(history=['Added by {0}'.format(self.request.user)])

        if details.get('journal'):
            model = models.Article
            if not details.get('journal_id'):
                j = models.Journal.objects.create(**details['journal'])
            else:
                j = models.Journal.objects.get(pk=details.get('journal_id'))
            info.update(journal=j)

            info.update({f: details.get(f) for f in ['volume', 'number', 'pages'] if details.get(f)})
        elif details['kind'] in models.Book.TYPES:
            model = models.Book
            info.update(
                {f: details.get(f) for f in ['main_title', 'editor', 'publisher', 'edition', 'address', 'volume', 'pages'] if details.get(f)}
            )
        elif details['kind'] in models.Patent.TYPES:
            model = models.Patent
        else:
            messages.add_message(self.request, messages.ERROR, "Unable to create publication: Unknown type")
            return HttpResponseRedirect(self.get_success_url())

        obj = data.get('obj', None)
        if not obj:
            obj = model.objects.create(**info)
        else:
            info['history'] = obj.history + ['Re-entered by {0} on {1}'.format(self.request.user, timezone.now().isoformat(' '))]
            model.objects.filter(pk=obj.pk).update(**info)

        if data.get('beamlines'):
            bls = {bl for bl in data['beamlines'] if not bl.kind == bl.TYPES.sector}
            for bl in [x for x in data['beamlines'] if (x.kind == x.TYPES.sector)]:
                bls.update(bl.children.all())
            data['beamlines'] = bls
            obj.beamlines.add(*data['beamlines'])
        if data.get('funders'):
            funders = [f if isinstance(f, models.FundingSource) else models.FundingSource.objects.create(**f) for f in data['funders']]
            obj.funders.add(*funders)
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
                    info = json.loads(cleaned_data['details'])
                    kind = info.get('kind', None)

                    if info:
                        details = {
                            'kind': kind, 'funders': info.get('funders', {}), 'unknown_funders': info.get('unknown_funders', {})
                        }
                        if kind in models.Article.TYPES:
                            journal = None
                            for issn in info.get('journal', {}).get('issn', '').split(';'):
                                js = models.Journal.objects.filter(issn__icontains=issn)
                                if js.count():
                                    journal = js[0]
                                    details['journal_id'] = journal.pk
                                    break
                            details['journal'] = info.get('journal', None)

                            fields = ['title', 'authors', 'date', 'volume', 'number', 'pages', 'reviewed', 'keywords', 'journal']
                            details.update({f: info.get(f, None) for f in fields})
                            details.update(
                                {
                                    'journal_title': journal and journal.title or details.get('journal', {}).get(
                                        'title', ''
                                    ), 'code': info.get('code', None)
                                }
                            )

                        elif kind in ['msc_thesis', 'phd_thesis']:
                            details = info
                        elif kind in models.Book.TYPES:
                            if 'isbn' in info:
                                details['code'] = info.get('isbn', None)
                                fields = [
                                    'main_title', 'editor', 'publisher', 'title', 'authors', 'edition', 'address', 'volume', 'pages',
                                    'keywords', 'date'
                                ]
                            elif 'book' in info:
                                details.update({'code': info.get('code', None), 'edition': info.get('number', None)})
                                details.update(
                                    {f: info['book'].get(f, None) for f in ['main_title', 'publisher', 'editor']}
                                )
                                fields = ['title', 'authors', 'volume', 'pages', 'date', 'keywords']

                        elif kind in models.Patent.TYPES:
                            fields = ['title', 'authors', 'date', 'keywords']
                            details.update({f: info.get(f, None) for f in fields})
                            details['code'] = info.get('number', "").strip()

                        form_info['details'] = json.dumps(details)

            elif step == "2" or self.form_list['2'] == form.__class__:

                cleaned_data = self.get_cleaned_data_for_step('1') or {}
                try:
                    details = json.loads(cleaned_data.get('details', '{}'))
                except:
                    details = {}
                kind = details.get('kind', cleaned_data.get('kind', None))

                details.update(
                    {f: cleaned_data[f] for f in list(cleaned_data.keys()) if f != 'details' and not details.get(f, None)}
                )

                matches = models.check_unique(
                    details.get('title', None), details.get('authors', None), details.get('code', None)
                )

                if 'thesis' in kind:
                    for f in ['title', 'authors', 'publisher', 'address', 'keywords', 'kind', 'code']:
                        details.update({f: cleaned_data.get(f, None)})

                    if cleaned_data.get('date', None):
                        details['date'] = cleaned_data['date'].isoformat()

                form_info = {
                    'details': json.dumps(details), 'kind': kind, 'obj': matches and matches[0] or None
                }

                funders = []
                for f in details.get('funders', []):
                    fs = models.FundingSource.objects.filter(doi__icontains=f['doi'])
                    if fs.count():
                        funders.append(fs[0])
                    else:
                        funders.append(f)
                for f in details.get('unknown_funders', []):
                    fs = models.FundingSource.objects.filter(name__icontains=f['name'])
                    if fs.count():
                        funders.append(fs[0])
                form_info['funders'] = funders

            if form_info:
                form.initial = form_info
            form.update_helper()

        return form


def abbrev_author(name):
    parts = [x.strip() for x in name.strip().split(',')]
    if len(parts) > 1:
        return "{}, {}".format(parts[0].upper(), '' if not parts[1] else parts[1][0].upper())
    else:
        return name.strip().upper()


class InstitutionMetrics(RolePermsViewMixin, TemplateView):
    admin_roles = ['publications-admin']
    allowed_roles = ['employee']
    template_name = "publications/institution_metrics.html"

    def get_context_data(self, **kwargs):
        from users.models import Institution
        context = super().get_context_data(**kwargs)

        institution = Institution.objects.get(pk=self.kwargs.get('pk'))
        context['institution'] = institution
        authors = {"{}, {}".format(u.last_name.upper(), u.first_name[0]) for u in institution.users.all()}
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
