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
