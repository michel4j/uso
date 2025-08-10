from .models import Publication
from collections import defaultdict, OrderedDict
from misc.stats import DataTable
from datetime import date
from django.utils.safestring import mark_safe
from django.db.models import Count, Avg, Sum, Q
import itertools
import re


def html2text(html):
    html = re.sub(r'[\s\n]+', ' ', html)
    html = re.sub(r'<[^<]*?>', '', html)
    return html


def summarize_funding(qset):
    stats = {f: {'total': 0, 'year': defaultdict(int)} for f in qset}

    for f in qset:
        for p in Publication.objects.filter(funders=f):
            stats[f]['total'] += 1
            stats[f]['year'][p.date.year] += 1

    yrs = sorted({v['date'].year for v in Publication.objects.values("date").order_by("date").distinct()})
    cols = ['Funding Agency'] + yrs + ['Total']
    _tbl = [cols]
    for f in qset:
        r = [stats[f]['year'][yr] for yr in yrs]
        if sum(r) > 0:
            r = [mark_safe(f.html_display())] + r + [sum(r)]
            _tbl.append(r)
    return DataTable(_tbl)


def summarize_activity(qset):
    types = [k for k, _ in Publication.TYPES]
    today = date.today()
    y4rs = [today.year + x for x in [-3, -2, -1, 0]]
    y4rl = "{0}-{1}".format(y4rs[0], today.strftime('%y'))
    stats = {k: {'total': 0, 'year': defaultdict(int), y4rl: 0} for k in types}

    for p in qset.all():
        yr = p.date.year
        k = p.kind
        stats[k]['total'] += 1
        stats[k]['year'][yr] += 1
        if yr in y4rs:
            stats[k][y4rl] += 1

    yrs = sorted({v['date'].year for v in Publication.objects.values("date").order_by("date").distinct()})
    cols = [''] + yrs + [y4rl, 'All']
    _tbl = [cols]
    for k in types:
        r = [stats[k]['year'][yr] for yr in yrs]
        if sum(r) > 0:
            r = [Publication.TYPES[k]] + r + [stats[k][y4rl]] + [sum(r)]
            _tbl.append(r)
    r = ['Total'] + [sum(xr[1:]) for xr in list(zip(*_tbl))[1:]]
    rem_col = []
    for i, v in enumerate(r):
        if v == 'Total': continue
        if v > 0:
            break
        else:
            rem_col.append(i)

    _tbl.append(r)
    data_table = DataTable(_tbl, plot_limits=[-1, -2])
    data_table.remove_columns(rem_col)
    return data_table


def get_publist(qset):
    stats = OrderedDict()
    types = [k for k, _ in Publication.TYPES]
    yrs = sorted({v['date'].year for v in Publication.objects.values("date").order_by("date").distinct()})
    for k in types:
        plist = [(yr, qset.filter(kind=k, date__year=yr).all().order_by('authors')) for yr in
                 reversed(yrs)]
        stats[Publication.TYPES[k]] = [p for p in plist if p[1].count()]
    stats = {k: v for k, v in list(stats.items()) if v}
    return list(stats.items())


def get_activity(qset):
    from . import models
    descriptions = {
        models.Publication.CATEGORIES.beamline: "Publications reporting results based on data acquired at one or more CLS beamline",
        models.Publication.CATEGORIES.design: "Publications describing beamlines, endstations, or their design but does not include data acquired using photons",
        models.Publication.CATEGORIES.facility: "Publications describing the facility as a whole, accelerators, diagnostic systems not specific to any beamline",
        models.Publication.CATEGORIES.dataless: "Publications by CLS staff which do not use data from the CLS, and are not CLS-related",
    }
    _tbl = summarize_activity(qset)
    _tbl.heading = "Overall activity"
    _tbl.sub_heading = "All publications"
    tables = [_tbl]
    for category, description in list(descriptions.items()):
        _tbl = summarize_activity(qset.filter(category=category))
        _tbl.heading = models.Publication.CATEGORIES[category]
        _tbl.sub_heading = description
        tables.append(_tbl)

    for area in models.SubjectArea.objects.exclude(pk=1).filter(Q(category__isnull=True) | Q(category__pk=1)).order_by(
            "-category"):
        _qset = qset.filter(areas=area).distinct()
        if not _qset.count(): continue
        _tbl = summarize_activity(_qset)
        _tbl.heading = area.name
        tables.append(_tbl)

    return tables


def get_metrics(qset, single=False):
    from beamlines.models import Facility
    metric_tables = []
    keys = [
        ('articles', 'Articles'),
        # ('num_cites', 'Citations'),
        # ('avg_cites', 'Mean Citations'),
        ('avg_sjr', 'Mean SJR Rank'),
        ('avg_ifactor', 'Mean Impact Factor'),
        ('avg_hindex', 'Mean H-Index')
    ]
    aggrs = {
        'articles': Count('pk'),
        # 'num_cites': Sum('citations'),
        # 'avg_cites': Avg('citations'),
        'avg_sjr': Avg('journal__sjr'),
        'avg_ifactor': Avg('journal__ifactor'),
        'avg_hindex': Avg('journal__hindex')
    }
    yrs = qset.dates('date', 'year', order='ASC')
    _tbl = [[''] + [k[1] for k in keys]]
    for yr in yrs:
        data = qset.filter(date__year=yr.year).aggregate(**aggrs)
        _tbl.append([yr.year] + [data[k[0]] for k in keys])

    # 3year period
    today = date.today()
    yr3ago = today.replace(year=today.year - 3,
                           day=today.day - 1 if (today.day == 29) and (today.month == 2) else today.day)
    yr3name = "{0}-{1}".format(yr3ago.year, today.strftime('%y'))
    data = qset.filter(date__gte=yr3ago).aggregate(**aggrs)
    _tbl.append([yr3name] + [data[k[0]] for k in keys])

    # Total
    data = qset.aggregate(**aggrs)
    all_row = ['All'] + [data[k[0]] for k in keys]  # reused for the remaining
    _tbl.append(all_row)
    _dt = DataTable(_tbl, heading="Quality Metrics by Year", max_cols=15, plot_limits=[None, -2])
    _dt.reverse()
    metric_tables.append(_dt)

    if not single:
        bls = Facility.objects.order_by('kind', 'acronym').values_list('acronym', flat=True)
        _tbl = [[''] + [k[1] for k in keys]]
        for bl in bls:
            data = qset.filter(Q(beamlines__acronym=bl) | Q(beamlines__parent__acronym=bl)).distinct().aggregate(
                **aggrs)
            _r = [bl] + [data[k[0]] for k in keys]
            if not _r[1]: continue
            _tbl.append([bl] + [data[k[0]] for k in keys])

        # Total 
        _tbl.append(all_row)
        metric_tables.append(DataTable(_tbl, heading="Quality Metrics by Beamline/Sector/Village", max_cols=13))

    categories = qset.filter(category__isnull=False).values_list('category', flat=True).distinct()
    _tbl = [[''] + [k[1] for k in keys]]
    for cat in categories:
        data = qset.filter(category=cat).aggregate(**aggrs)
        _tbl.append([Publication.CATEGORIES[cat]] + [data[k[0]] for k in keys])
    # Total   
    _tbl.append(all_row)
    metric_tables.append(DataTable(_tbl, heading="Quality Metrics by Category", max_cols=15))

    _tbl = [['Cites', 'Publication', 'Beamlines'], ]
    ctpubs = qset.order_by('-citations')[:10]
    for p in ctpubs:
        _tbl.append([p.citations, html2text(p.cite()), ', '.join([b.acronym for b in p.beamlines.all()])])
    metric_tables.append(
        DataTable(_tbl, heading="Top 10 Most Cited Articles", css_class="text-table", plot_limits=[None, -2]))
    return metric_tables


STOPWORDS = re.compile(
    r"\s(i|me|my|myself|we|us|our|ours|ourselves|you|your|yours|yourself|yourselves|he|him|his|himself|she|her|hers|"
    r"herself|it|its|itself|they|them|their|theirs|themselves|what|which|who|whom|whose|this|that|these|those|am|is|"
    r"are|was|were|be|been|being|have|has|had|having|do|does|did|doing|will|would|should|can|could|ought|i'm|you're|"
    r"he's|she's|it's|we're|they're|i've|you've|we've|they've|i'd|you'd|he'd|she'd|we'd|they'd|i'll|you'll|he'll|"
    r"she'll|we'll|they'll|isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't|doesn't|don't|didn't|won't|wouldn't|"
    r"shan't|shouldn't|can't|cannot|couldn't|mustn't|let's|that's|who's|what's|here's|there's|when's|where's|why's|"
    r"how's|a|an|the|and|but|if|or|because|as|until|while|of|at|by|for|with|about|against|between|into|through|during|"
    r"before|after|above|below|to|from|up|upon|down|in|out|on|off|over|under|again|further|then|once|here|there|when|"
    r"where|why|how|all|any|both|each|few|more|most|other|some|such|no|nor|not|only|own|same|so|than|too|very|say|says|"
    r"said|shall)\s"
)
SEPARATORS = re.compile(r"([&,:;\s\u3031-\u3035\u309b\u309c\u30a0\u30fc\uff70]+)")


def get_keywords(queryset, transform=float, max_size=60):
    cloud = defaultdict(int)
    txt = " ".join(
        itertools.chain.from_iterable([p.keywords + [p.title] for p in queryset.all() if p.keywords])).lower()
    # txt = u" ".join([p.title for p in queryset.all()]).lower()
    txt = re.sub(STOPWORDS, ' ', txt)
    txt = re.sub(SEPARATORS, ' ', txt)
    for kw in txt.split():
        if len(kw) < 4:
            continue
        cloud[kw] += 1
    _mx = cloud and transform(max(cloud.values())) or 0.0
    kwcloud = [{'text': k, 'size': max_size * transform(v) / _mx} for k, v in list(cloud.items())]
    kwcloud.sort(key=lambda v: v['size'], reverse=True)
    return kwcloud[:100]
