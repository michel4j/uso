from django import template
from django.db.models import Q, Count
from django.utils.safestring import mark_safe
from publications import stats
from publications.models import Publication, check_unique
from beamlines.models import Facility
import json
import re
from datetime import datetime
from publications import models

register = template.Library()

CAT_COLORS = ['#7eb852', '#07997e', '#4f54a8', '#991c71', '#cf003e', '#e3690b', '#efb605', '#a5a5a5']
ALT_COLORS = ['#1F77B4', '#AEC7E8', '#FF7F0E', '#FFBB78', '#41A42D', '#98DF8A', '#D62728', '#FF94C8']


@register.filter(name="get_table_quality")
def get_table_quality(tbl):
    data = []
    xvals = tbl.pop(0)
    types = get_measures(None, tbl)
    for t in types:
        line = [entry for entry in tbl if entry[0] == t] or [None]
        entries = []
        for i, yr in enumerate(xvals):
            if i and isinstance(yr, int):
                entries.append({'x': yr, 'y': line[0] and line[0][i] or 0})
        data.append({str(t): entries})
    return data


@register.simple_tag(takes_context=True)
def show_funding(context):
    tbl = stats.summarize_funding(
        models.FundingSource.objects.annotate(npubs=Count('publications')).exclude(npubs=0).distinct().order_by(
            '-npubs')[:20])
    return tbl.html({'class': 'table table-hover'})


@register.simple_tag(takes_context=True)
def get_activity_tables(context):
    tables = stats.get_activity(Publication.objects.all())
    return tables


@register.simple_tag(takes_context=True)
def get_beamline_activity(context, qset):
    return stats.summarize_activity(qset)


@register.simple_tag(takes_context=True)
def cite(context, obj):
    template_name = f'publications/citations/{obj.__class__.__name__.lower()}.html'
    t = template.loader.get_template(template_name)
    return mark_safe(t.render({'pub': obj}))


@register.filter(name="get_citation")
def get_citation(cls="article", data="{}"):
    cls = {
        'msc_thesis': 'book',
        'phd_thesis': 'book',
        'chapter': 'book',
        'pdb': 'pdb',
        'patent': 'patent',
        'proceeding': 'article',
        'magazine': 'article',
        'article': 'article',
    }.get(cls, 'default')

    pub = json.loads(data)
    if isinstance(pub.get('authors', []), list):
        pub['authors'] = '; '.join(pub.get('authors', []))
    try:
        pub['date'] = datetime.strptime(pub['date'], "%Y-%M-%d")
    except ValueError:
        pass
    template_name = f'publications/citations/{cls}.html'
    t = template.loader.get_template(template_name)
    return mark_safe(t.render({'pub': pub}))


@register.simple_tag(takes_context=True)
def get_colors(context):
    return CAT_COLORS


@register.simple_tag(takes_context=True)
def get_types(context):
    return [str(k) for _, k in Publication.TYPES]


@register.simple_tag(takes_context=True)
def get_beamlines(context):
    beamlines = [b.acronym for b in Facility.objects.exclude(kind=Facility.Types.sector) if b.publications.count() > 0]
    beamlines = [b.acronym for b in Facility.objects.filter(kind=Facility.Types.sector)]
    return beamlines


@register.simple_tag(takes_context=True)
def get_measures(context, tbl):
    return [tbl[i][0] for i in range(0, len(tbl))]


@register.filter(name="clean_name")
def clean_name(name):
    pattern = re.compile(r'[\W_]+')
    return pattern.sub('', name)


@register.simple_tag(takes_context=True)
def show_table(context, tbl):
    html = tbl.html({'class': 'table table-hover table-condensed'})
    return html


@register.simple_tag(takes_context=True)
def my_pub_count(context):
    return context['user'].publications.count()


@register.simple_tag(takes_context=True)
def get_quality_tables(context):
    facility = context.get('beamline')
    acronym = None if not facility else facility.acronym
    if acronym:
        qset = models.Article.objects.filter(
            beamlines__parent__acronym__iexact=acronym, kind='article'
        ) | models.Article.objects.filter(
            beamlines__acronym__iexact=acronym, kind='article'
        )
        single = True
    else:
        qset = models.Publication.objects.filter(kind='article')
        single = False
    return stats.get_metrics(qset.distinct(), single)


@register.tag
def get_bt_quality_tables(parser, token):
    return BTQTNode()


class BTQTNode(template.Node):

    def render(self, context):
        facility = context.get('beamline')
        acronym = None if not facility else facility.acronym
        qset = models.Article.objects.filter(pk__in=facility.details.get('beamteam_publications', []),
                                             kind='article').distinct()
        single = True
        context['quality_tables'] = stats.get_metrics(qset.distinct(), single)
        return ''


@register.simple_tag(takes_context=True)
def my_claim_count(context):
    user = context['user']
    if user.is_authenticated:
        qf = Q(authors__icontains='{0}, {1}'.format(user.last_name, user.first_name[0]))
        if user.preferred_name:
            qf |= Q(authors__icontains='{0}, {1}'.format(user.last_name, user.preferred_name[0]))
        if user.other_names:
            qf |= Q(authors__icontains='{0}, {1}'.format(user.other_names, user.first_name[0]))
            qf |= Q(authors__icontains='{0}, {1}'.format(user.last_name, user.other_names[0]))
    else:
        qf = Q(authors__icontains='xxxxxx')
    return models.Publication.objects.filter(qf).exclude(users__id__exact=user.pk).count()


@register.filter(name='get_matches')
def get_matches(obj):
    return check_unique(obj.title, obj.authors, None).exclude(pk=obj.pk)


@register.simple_tag(takes_context=True)
def bt_claim_count(context):
    bl = context['bl']
    qf = Q(authors__icontains='xxxxxx')
    if bl.details.get('beamteam', None):
        for btm in bl.details.get('beamteam', '').split(';'):
            last_name = btm.split(', ')[0]
            first_name = btm.split(', ')[1]
            qf |= Q(authors__icontains='{0}, {1}'.format(last_name, first_name[0]))
    qf |= Q(kind__in=[models.Publication.TYPES.msc_thesis, models.Publication.TYPES.phd_thesis])
    qf &= (Q(beamlines__parent__acronym__iexact=bl.acronym) | Q(beamlines__acronym__iexact=bl.acronym))
    queryset = models.Publication.objects.filter(qf).exclude(
        pk__in=bl.details.get('beamteam_publications', [])).distinct().all()
    return queryset.count()


@register.simple_tag(takes_context=True)
def bt_pub_count(context):
    bl = context['bl']
    return models.Publication.objects.filter(pk__in=bl.details.get('beamteam_publications', [])).distinct().count()
