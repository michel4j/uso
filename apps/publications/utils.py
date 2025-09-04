import codecs
import copy
import csv
import itertools
import json
import operator
import os
import pickle
import re
import time
from collections import defaultdict
from datetime import date, timedelta
from functools import reduce
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
from charset_normalizer.md import lru_cache
from dateutil import parser
from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import dateparse, timezone
from habanero import Crossref
from lxml import etree

from misc.utils import MultiKeyDict
from . import models

PDB_SITE = getattr(settings, 'USO_PDB_SITE', 'CLSI')
PDB_SITE_MAP = getattr(settings, 'USO_PDB_SITE_MAP', {})

CROSSREF_API_EMAIL = getattr(settings, 'CROSSREF_API_EMAIL', '')
OPEN_CITATIONS_API_KEY = getattr(settings, 'OPEN_CITATIONS_API_KEY', None)
CROSSREF_THROTTLE = getattr(settings, 'CROSSREF_THROTTLE', 0.025)  # time delay between crossref calls
CROSSREF_BATCH_SIZE = getattr(settings, 'CROSSREF_BATCH_SIZE', 10)
GOOGLE_API_KEY = getattr(settings, 'GOOGLE_API_KEY', None)

OPEN_CITATIONS_URL = "https://opencitations.net/index/api/v2/"
CROSSREF_EVENTS_URL = "https://api.eventdata.crossref.org/v1/events/distinct"
CROSSREF_CITATIONS_URL = "https://www.crossref.org/openurl/"
PDB_SEARCH_URL = getattr(settings, 'PDB_SEARCH_URL', "https://search.rcsb.org/rcsbsearch/v2/query")
PDB_REPORT_URL = getattr(settings, 'PDB_REPORT_URL', "https://data.rcsb.org/graphql")
GOOGLE_BOOKS_API = getattr(settings, 'GOOGLE_BOOKS_API', "https://www.googleapis.com/books/v1/volumes")
SCIMAGO_URL = getattr(settings, 'SCIMAGO_URL', "https://www.scimagojr.com/journalrank.php")


SEARCH_JSON = {
    'query': {
        'type': 'group',
        'logical_operator': 'and',
        'nodes': [
            {
                'type': 'terminal',
                'service': 'text',
                'parameters': {
                    'attribute': 'diffrn_source.pdbx_synchrotron_site',
                    'operator': 'exact_match',
                    'negation': False,
                    'value': "CLSI",
                }
            },
            {
                'type': 'terminal',
                'service': 'text',
                'parameters': {
                    'attribute': 'rcsb_accession_info.revision_date',
                    'operator': 'greater',
                    'negation': False,
                    'value': '2025-01-01'
                }
            }
        ]
    },
    "return_type": "entry",
    "request_options": {
        "return_all_hits": True
    }
}

REPORT_QUERY = """{{
  entries(entry_ids: [{0}]) {{
    rcsb_id
    struct {{
      title
    }}
    rcsb_accession_info {{
      initial_release_date
      deposit_date
    }}
    rcsb_entry_info {{
      diffrn_resolution_high {{
        provenance_source
        value
      }}
    }}
    diffrn_detector {{
      pdbx_collection_date
    }}
    diffrn_source {{
      pdbx_synchrotron_beamline
      pdbx_synchrotron_site
    }}
    rcsb_primary_citation {{
      rcsb_authors
      pdbx_database_id_DOI
      year
    }}
  }}
}}"""

PDB_QUERY_DATA = [
    'rcsb_id',
    'struct.title',
    'rcsb_primary_citation.rcsb_authors',
    'rcsb_primary_citation.pdbx_database_id_DOI',
    'rcsb_accession_info.initial_release_date',
    'diffrn_source.pdbx_synchrotron_beamline',
    'diffrn_source.pdbx_synchrotron_site',
]


def flatten(d, parent_key='') -> dict:
    """
    Flattens a nested dictionary, concatenating keys with dots.

    :param d: The dictionary to flatten.
    :param parent_key: The prefix for keys (used in recursion).
    :return: A flat dictionary with dot-separated keys.
    """
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten(v, new_key))
        else:
            items[new_key] = v
    return items


class CrossRef(Crossref):
    def __init__(self):
        super().__init__(mailto=CROSSREF_API_EMAIL, ua_string='USO')

    def mentions(self, doi, year=None):
        headers = {
            'Accept': 'application/json',
        }
        params = {
            'mailto': self.mailto,
            'obj-id': doi,
            'rows': 1000,
        }
        if year:
            params['from-occurred-date'] = f'{year}-01-01'
            params['until-occurred-date'] = f'{year}-12-31'

        events = []
        more_results = True
        while more_results:
            response = requests.get(CROSSREF_EVENTS_URL, params=params, headers=headers)
            if response.status_code == 200:
                result = response.json()
                message = result.get('message', {})
                new_events = message.get('events', [])
                events.extend(new_events)
                total_events = message.get('total-results', 0)
                more_results = len(new_events) and (len(events) < total_events)
                params['cursor'] = message.get('next-cursor', None)
            else:
                more_results = False
        if not events:
            return {}

        df = pd.DataFrame(events)
        df['year'] = df.timestamp.str[:4]
        mentions = df.groupby('year').size().to_dict()

        if year:
            # if year is specified, return only that year
            return mentions.get(str(year), 0)
        return mentions


class OpenCitations:
    def __init__(self, api_key=None, rate_limit=10):
        self.rate_limit = rate_limit
        self.api_key = api_key or OPEN_CITATIONS_API_KEY
        self.base_url = OPEN_CITATIONS_URL
        self.headers = {
            'Accept': 'application/json',
            'authorization': self.api_key,
        }

    def citations_list(self, doi, year: int = None) -> list[dict]:
        """
        Get the list of citations for a given DOI from OpenCitations API.

        :param doi: The DOI of the publication.
        :param year: Optional year to filter results by.
        :return: Citations as a list of dicts
        """
        filters = '?filter=creation={year}' if year else ''
        url = f"{self.base_url}citations/doi:{doi}{filters}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"Error fetching citations for {doi}: {response.status_code}")
            return []

    def citations(self, doi, year: int = None) -> dict:
        """
        Get the number of citations for a given DOI from OpenCitations API.
        :param doi: The DOI of the publication.
        :param year: Optional year to filter results by.
        :return: dictionary mapping a year to a dictionary containing the number of citations
        """
        citations = self.citations_list(doi, year=year)
        if not citations:
            return {}

        df = pd.DataFrame(citations)
        df['year'] = df.creation.str[:4]
        all_cites = df.groupby('year').size().to_dict()
        self_cites = df.loc[df['author_sc'] == 'yes'].groupby('year').size().to_dict()
        years = set(all_cites.keys()).union(set(self_cites.keys()))
        info = {
            yr: {
                'citations': all_cites.get(yr, 0),
                'self_cites': self_cites.get(yr, 0)
            }
            for yr in sorted(years)
        }
        if year:
            # if year is specified, return only that year
            return info.get(str(year), {'citations': 0, 'self_cites': 0})
        return info


class ObjectParser(object):
    KEY_MAPS = {}
    FIELDS = []

    def __init__(self, entry):
        self._entry = entry

    def __getitem__(self, key):
        if isinstance(key, str):
            cleaner = f'get_{key}'
            if hasattr(self, cleaner):
                func = getattr(self, cleaner)
                return func()
            elif key in self.KEY_MAPS:
                return self._entry.get(self.KEY_MAPS[key])
            elif key in self._entry:
                return self._entry.get(key)
        else:
            raise TypeError("Invalid argument type.")

    def dict(self):
        return {
            field: self[field]
            for field in self.FIELDS
        }


class PDBParser(ObjectParser):
    """
    Used to extract Deposition specific data suitable for storing in the database
    from an RSCB API custom report entry

    """
    FIELDS = [
        'code', 'title', 'authors', 'date', 'kind', 'pdb_doi'
    ]
    KEY_MAPS = {
        'code': 'rcsb_id',
        'title': 'struct.title',
        'authors': 'rcsb_primary_citation.rcsb_authors',
    }

    def get_authors(self):
        return self._entry.get('rcsb_primary_citation.rcsb_authors', [])

    def get_date(self):
        return parser.isoparse(self._entry['rcsb_accession_info.initial_release_date'])

    def get_code(self):
        return f"{self._entry['rcsb_id'].upper()}"

    def get_kind(self):
        return models.Publication.TYPES.pdb

    def get_pdb_doi(self):
        if self._entry.get('rcsb_primary_citation.pdbx_database_id_DOI'):
            return self._entry['rcsb_primary_citation.pdbx_database_id_DOI']

    def get_beamlines(self):
        return [
            PDB_SITE_MAP.get(key)
            for key in self._entry['diffrn_source.pdbx_synchrotron_beamline'].split()
        ]


def fix_issns(issns: list) -> list:
    """
    Fix issn formatting
    :param issns: list of strings
    :return: list of strings with issns formatted correctly
    """

    return [
        re.sub(r'(\w{4})(?!$)', r'\1-', issn.replace('-', '').strip())
        for issn in issns
    ] or []


class BookParser(ObjectParser):
    """
    Used to extract book specific data suitable for storing in the database
    from a Google books API report entry

    """
    FIELDS = ['date', 'authors', 'code', 'abstract', 'kind', 'title', 'publisher']
    BOOK_KIND = models.Publication.TYPES.book
    KEY_MAPS = {
        'abstract': 'description',
    }

    def get_code(self):
        return f'{self._entry["industryIdentifiers"][0]["identifier"]}'

    def get_date(self):
        if len(self._entry['publishDate']) == 4:
            d = dateparse.parse_date(f'{self._entry["publishDate"]}-01-01')
        elif len(self._entry['publishDate']) == 7:
            d = dateparse.parse_date(f'{self._entry["publishDate"]}-01')
        else:
            d = dateparse.parse_date(self._entry['publishDate'])
        return d.isoformat()

    def get_kind(self):
        return self.BOOK_KIND

    def get_authors(self):
        return '; '.join(self._entry['authors'])

    def get_title(self):
        return '; '.join(
            filter(
                None, [
                    self._entry['title'],
                    self._entry.get('subtitle', '')
                ]
            )
        )


class ArticleParser(ObjectParser):
    """
    Used to extra article specific data suitable for storing in the database
    from a CrossRef report entry

    """
    KEY_MAPS = {
        'topics': 'subject',
        'pages': 'page',
        'publisher': 'publisher',
    }

    FIELDS = [
        'date', 'authors', 'code', 'kind', 'title', 'publisher', 'volume', 'issue', 'pages', 'journal',
        'journal_metric', 'funders'
    ]

    # map crossref work types to PublicationTypes
    TYPES_MAP = {
        'reference-book': models.Publication.TYPES.book,
        'proceedings-article': models.Publication.TYPES.proceeding,
        'dissertation': models.Publication.TYPES.phd_thesis,
        'edited-book': models.Publication.TYPES.book,
        'journal-article': models.Publication.TYPES.article,
        'report': models.Publication.TYPES.book,
        'book-track': models.Publication.TYPES.book,
        'standard': models.Publication.TYPES.book,
        'book-section': models.Publication.TYPES.chapter,
        'book-part': models.Publication.TYPES.chapter,
        'book': models.Publication.TYPES.book,
        'book-chapter': models.Publication.TYPES.chapter,
        'monograph': models.Publication.TYPES.book,
    }

    def get_code(self):
        return self._entry['DOI']

    def get_date(self):
        """
        Generate a valid publish date, start with online, then hard and if not available,
        use the created date.

        :return: a date object
        """
        online = self._entry.get('published-online')
        hard = self._entry.get('published-print')
        created = self._entry.get('created')
        if online:
            parts = online['date-parts'][0]
        elif hard:
            parts = hard['date-parts'][0]
        else:
            parts = created['date-parts'][0]

        parts = parts + [1] * (3 - len(parts))  # sometimes partial dates are given, assume first of month
        return date(*parts)

    def get_authors(self):
        return [
            f'{author["family"]}, {author.get("given", "")}'
            for author in self._entry['author']
        ]

    def get_kind(self):
        if self._entry['type'] == 'dissertation':
            degree = '; '.join(self._entry.get('degree'))
            if 'PhD' in degree or 'Doctor' in degree:
                return models.Publication.TYPES.phd_thesis
            elif 'MSc' in degree or 'Master' in degree:
                return models.Publication.TYPES.msc_thesis
            else:
                return models.Publication.TYPES.phd_thesis
        return self.TYPES_MAP.get(self._entry['type'], models.Publication.TYPES.magazine)

    def get_title(self):
        return '; '.join(self._entry['title'])

    def get_funders(self):
        return [
            {
                'name': funder['name'],
                'doi': funder.get('DOI'),
            }
            for funder in self._entry.get('funder', [])
        ]

    @lru_cache(maxsize=128)
    def get_journal(self):
        issns = tuple(set(fix_issns(self._entry.get('ISSN', []))))
        names = self._entry.get('short-container-title', [])
        names += self._entry.get('container-title', [])
        names.sort(key=lambda v: len(v))
        names = list(filter(None, names))
        issn_query = reduce(operator.__or__, [Q(codes__icontains=issn) | Q(issn__iexact=issn) for issn in issns], Q())
        journal = models.Journal.objects.filter(issn_query).distinct().first()
        if journal:
            return journal.pk
        elif issns:
            return {
                'title': '; '.join(self._entry.get('container-title', [])),
                'codes': tuple(set(issns)),
                'publisher': self._entry.get('publisher'),
                'short_name': names[0]
            }

    def get_journal_metric(self):
        journal = self.get_journal()
        d = self.get_date()

        if isinstance(journal, int):
            return models.JournalMetric.objects.filter(journal=journal, year=d.year).order_by('-year').first()
        return None

    def get_main_title(self):
        if self._entry['type'] in ['book-part', 'book-section', 'book-chapter']:
            return '; '.join(self._entry['container-title'])

    def get_isbn(self):
        return self._entry.get('ISBN', [])

    def get_affiliations(self):
        return list(
            {
                inst['name']: {
                    'name': inst['name'],
                    'acronym': inst.get('acronym', ''),
                    'place': ', '.join(inst.get('place', [])),
                    'ror': inst.get('ROR', ''),
                }
                for auth in self._entry.get('author', [])
                for inst in auth.get('affiliation', [])
            }.values()
        )


class JournalParser(ObjectParser):
    """
    Used to extract journal specific data suitable for storing in the database
    from a CrossRef report entry

    """
    KEY_MAPS = {
        'publisher': 'publisher',
    }

    FIELDS = [
        'title', 'codes', 'publisher',
    ]

    def get_codes(self):
        return tuple(set(fix_issns(self._entry.get('ISSN', []))))

    def get_topics(self):
        return [topic['name'] for topic in self._entry.get('subjects', [])]

    def get_asjc(self):
        return list(filter(None, [topic.get('ASJC') for topic in self._entry.get('subjects', [])]))


class SCIMagoParser(ObjectParser):
    FIELDS = ['h_index', 'impact_factor', 'sjr_rank', 'sjr_quartile', 'codes']

    @staticmethod
    def make_float(text):
        fixed_text = text.replace(',', '.')
        try:
            value = float(fixed_text)
        except ValueError:
            value = None
        return value

    def get_h_index(self):
        return self.make_float(self._entry['H index'])

    def get_impact_factor(self):
        return self.make_float(self._entry['Cites / Doc. (2years)'])

    def get_sjr_rank(self):
        return self.make_float(self._entry['SJR'])

    def get_sjr_quartile(self):
        return {
            'Q1': 1, 'Q2': 2, 'Q3': 3, 'Q4': 4
        }.get(self._entry['SJR Best Quartile'])

    def get_codes(self):
        return tuple(
            {
                re.sub(r'(\w{4})(?!$)', r'\1-', code.strip())
                for code in self._entry['Issn'].split(',')
            }
        )


def fetch_pdb_codes():
    """
    Retrieve all revised PDB Codes for the facility as a list of strings
    """
    dt = timezone.localtime(timezone.now() - timedelta(days=180))
    search = copy.deepcopy(SEARCH_JSON)
    search['query']['nodes'][0]['parameters']['value'] = PDB_SITE
    search['query']['nodes'][1]['parameters']['value'] = f"{dt:%Y-%m-%d}"
    codes = []
    try:
        response = requests.post(PDB_SEARCH_URL, json=search)
        if response.status_code == 200:
            result = response.json()
            codes = [item['identifier'].upper() for item in result.get('result_set', [])]
        else:
            response.raise_for_status()
    except Exception as e:
        print(f"Error fetching PDB codes: {e}")

    return codes


def fetch_pdb_entries(codes) -> list[dict]:
    """
    Fetch the CSV data for all specified PDB codes
    :param codes:  list of strings representing pdbcodes
    :return: a list of dictionaries one for each entry containing the report rows
    """

    params = REPORT_QUERY
    params = params.format(', '.join([f'"{pdb}"' for pdb in codes]))

    response = requests.post(PDB_REPORT_URL, json={'query': params})

    if response.status_code == 200:
        result = response.json()
        return result['data']['entries']
    else:
        response.raise_for_status()
        return []


def create_pdb_entries(entries):
    """
    Create database entries for PDB results
    :param entries: a list of dictionaries returned from PDB search reports
    :return: a dictionary representing the numbers of entries created or updated
    """
    from beamlines.models import Facility

    no_refs = models.Publication.objects.filter(
        kind=models.Publication.TYPES.pdb, reference__isnull=True
    ).distinct('code').in_bulk(field_name='code')

    old_entries = models.Publication.objects.filter(kind=models.Publication.TYPES.pdb).values_list('code', flat=True)

    new_entries = {}
    updated_entries = []

    entry_acronyms = defaultdict(list)  # a list of facility names for each pdb code

    for entry in entries:
        for i, src in enumerate(entry['diffrn_source']):
            if src['pdbx_synchrotron_site'] == PDB_SITE:
                break
        for k in ['diffrn_source', 'diffrn_detector']:
            entry[k] = entry.get(k) and entry.get(k, [])[i] or None
        entry = flatten(entry)

        record = PDBParser(entry)
        info = record.dict()

        if info['code'] in old_entries:
            # Update citation parameter if citation has changed
            if info['code'] in no_refs and record['reference'] and not no_refs[info['code']].pdb_doi:
                no_refs[info['code']].pdb_doi = record['reference']
                updated_entries.append(no_refs[info['code']])
        else:
            # New entries
            entry_acronyms[info['code']].extend(record['beamlines'])
            if not info['code'] in new_entries:  # entry will exist already for multi-beamline entries
                new_entries[info['code']] = models.Publication(**info)

    # update old entries if any changes have happened
    if updated_entries:
        models.Publication.objects.bulk_update(updated_entries, fields=['citation'])

    # create new entries if any
    if new_entries:
        models.Publication.objects.bulk_create(new_entries.values())

    # finally, add beamline relationships to newly created depositions:
    target_entries = models.Publication.objects.filter(
        code__in=entry_acronyms.keys()
    ).distinct('code').in_bulk(field_name='code')
    with transaction.atomic():
        for code, deposition in target_entries.items():
            deposition.beamlines.set(Facility.objects.filter(acronym__in=entry_acronyms[code]))
    return {'created': len(new_entries), 'updated': len(updated_entries)}


def fetch_book(isbn_list):
    """
    Given a list of book ISBN numbers, return metadata for the first entry
    that successfully resolves using Google's Books API

    :param isbn_list: list of ISBN numbers
    :return: book parser
    """

    for isbn in isbn_list:
        isbn = re.sub(r'[\s_-]', '', isbn)
        params = {'q': f'isbn:{isbn}', 'key': GOOGLE_API_KEY}
        response = requests.get(GOOGLE_BOOKS_API, params=params)
        if response.status_code == requests.codes.ok:
            result = response.json()
            if result['totalItems'] == 0:
                continue
            record = BookParser(result['items'][0]['volumeInfo'])
            return record.dict()
    return {}


def chunker(iterable, n):
    """
    Iterate through an iteratable in junks of at most n items
    :param iterable: iterator
    :param n: number of items in each chunk
    :return: returns an iterable with n items
    """

    class Filler(object): pass

    return (
        itertools.filterfalse(lambda x: x is Filler, chunk)
        for chunk in (itertools.zip_longest(*[iter(iterable)] * n, fillvalue=Filler))
    )


def create_publications(doi_list):
    """
    Given a list of dois, create database entries for the publications
    :param doi_list:
    :return: a dictionary representing the numbers of entries created
    """

    existing_pubs = set(models.Publication.objects.values_list('code', flat=True))
    existing_journals = MultiKeyDict(
        {
            tuple(codes): pk
            for codes, pk in models.Journal.objects.values_list('codes', 'pk')
        }
    )
    # avoid fetching exising entries
    pending_doi_list = list(set(doi_list) - existing_pubs)

    if not pending_doi_list:
        return {'journals': 0, 'publications': 0}

    # fetch metadata from CrossRef
    cr = CrossRef()
    results = cr.works(ids=pending_doi_list)

    # fix inconsistent JSON from works
    results = results if isinstance(results, list) else [results]

    new_publications = {}  # details of publications to create indexed by doi code
    new_journals = MultiKeyDict({})  # journals to create

    # first pass to create publication details
    for item in results:
        entry = ArticleParser(item['message'])
        details = entry.dict()

        if details['code'] in existing_pubs:
            # publication exists already
            continue

        if details['kind'] == models.Publication.TYPES.chapter:
            book_entry = fetch_book(entry['isbn'])
            details['main_title'] = book_entry['title']
            details['editor'] = book_entry['authors']
            details['publisher'] = book_entry['publisher']
        elif details['kind'] == models.Publication.TYPES.book:
            book_entry = fetch_book(entry['isbn'])
            details.update(book_entry.dict())
        else:
            journal = entry['journal']
            if isinstance(journal, dict):
                codes = journal['codes']
                if codes in existing_journals:
                    details['journal_id'] = existing_journals[codes]
                else:
                    # add journal details to new journals to create
                    new_journals[codes] = journal

                # keep issn for later use to swap for journal_id
                details['journal_issn'] = codes
            elif isinstance(journal, int):
                # journal_id is already set, no need to create a new journal
                details['journal_id'] = journal

        new_publications[details['code']] = details

    # Fetch new journal entries
    for codes, journal in new_journals.items():
        found = False
        for code in codes:
            try:
                results = cr.journals(ids=code)
                found = True
            except requests.exceptions.HTTPError as e:
                continue

            # update journal details in new journals
            entry = JournalParser(results['message'])
            new_journals[codes].update(entry.dict())
            break

    # now ready to create journals
    to_create = MultiKeyDict(
        {
            codes: models.Journal(**details) for codes, details in new_journals.items()
            if codes
        }
    )

    models.Journal.objects.bulk_create(to_create.values())

    # update journal_ids
    existing_journals = MultiKeyDict(
        {
            tuple(j.codes): j
            for j in models.Journal.objects.all()
        }
    )

    # update publication details
    for details in new_publications.values():
        if 'journal_issn' in details:
            details['journal'] = existing_journals[details.pop('journal_issn')]
        elif 'journal' in details and isinstance(details['journal'], int):
            details['journal_id'] = details.pop('journal', None)

    # create publication entries
    if new_publications:
        for details in new_publications.values():
            beamlines = details.pop('beamlines', [])
            funders = details.pop('funders', [])
            obj = models.Publication.objects.create(**details)

            if beamlines:
                items = {bl for bl in beamlines if not bl.kind == bl.Types.sector}
                for bl in [x for x in beamlines if (x.kind == x.Types.sector)]:
                    items.update(bl.children.all())
                obj.beamlines.add(*items)

            if funders:
                new_funders = []
                for funder in funders:
                    doi = funder.pop('doi', None)
                    if not doi:
                        continue
                    f, created = models.FundingSource.objects.get_or_create(doi=doi, defaults=funder)
                    new_funders.append(f)
                obj.funders.add(*new_funders)

    return {'journals': len(new_journals), 'publications': len(new_publications)}


def update_pdb_references(pending: QuerySet) -> dict:
    """
    Update PDB depositions with references from CrossRef if available
    :param pending: Queryset of pending depositions
    :return: dictionary containing number of "pdbs" updated, and number of "references" added
    """
    now = timezone.now()

    # Pending items are PDBs with pdb_doi but no reference
    pending_depositions = defaultdict(list)

    # multiple depositions can exist for the same DOI so group them together
    for deposition in pending:
        doi = re.sub(r'^https?://(dx\.)?doi\.org/', '', deposition.pdb_doi)
        pending_depositions[doi].append(deposition)

    # process doi in chunks of CROSSREF_BATCH_SIZE, to avoid issues with CrossRef rate limits
    for chunk in chunker(pending_depositions.keys(), CROSSREF_BATCH_SIZE):
        doi_list = list(chunk)
        create_publications(doi_list)
        time.sleep(CROSSREF_THROTTLE)

    # Update references
    added_references = models.Publication.objects.filter(
        kind=models.Publication.TYPES.pdb, created__gt=now
    ).distinct('code').in_bulk(
        pending_depositions.keys(), field_name='code'
    )

    for code, depositions in pending_depositions.items():
        for deposition in depositions:
            deposition.reference = added_references.get(code)

    models.Publication.objects.bulk_update(pending, fields=['reference'])

    return {'references': len(pending_depositions), 'pdbs': len(pending)}


def fetch_journal_metrics(year=None):
    """
    Fetch Journal Metrics for a given year from SJR
    :param year: Year
    :return: a dictionary containing metrics keyed by journal ISSN number
    """

    params = {
        'out': 'xls',
        'year': year if year else timezone.now().year
    }
    cache_dir = Path(settings.LOCAL_DIR) / 'cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    file_path = cache_dir / f'scimago-{params["year"]}.pickle'
    if os.path.exists(file_path):
        with open(file_path, 'rb') as handle:
            return pickle.load(handle)
    else:
        response = requests.get(SCIMAGO_URL, params=params)
        if response.status_code == 200:
            dialect = csv.Sniffer().sniff(response.text[:5000])
            text = codecs.iterdecode(response.iter_lines(), 'utf-8')
            reader = csv.DictReader(text, dialect=dialect)
            results = {
                obj.get_codes(): obj.dict()
                for row in reader
                for obj in [SCIMagoParser(row)]
            }
            with open(file_path, 'wb') as handle:
                pickle.dump(results, handle)
            return results


def update_journal_metrics(year=None):
    """
    Fetch and create journal metrics profile for current year or a given year
    :param year: Year or None
    :return: Number of profiles created and deleted
    """

    # fetch metrics for the year
    now = timezone.localtime(timezone.now())
    yr = year if year else now.year
    metrics_data = fetch_journal_metrics(yr)
    if not metrics_data:
        return {'created': 0, 'updated': 0}

    metrics = MultiKeyDict(metrics_data)

    # entries to be created
    target_journals = models.Journal.objects.filter(articles__date__year__lte=yr)
    to_create = [
        models.JournalMetric(journal=journal, year=yr, **metrics[tuple(journal.codes)])
        for journal in target_journals.exclude(metrics__year=yr).distinct()
        if tuple(journal.codes) in metrics
    ]
    models.JournalMetric.objects.bulk_create(to_create)

    # entries to update
    to_update = models.JournalMetric.objects.filter(year=yr, journal__in=target_journals).distinct('journal')
    num_updated = 0
    for metric in to_update:
        codes = tuple(metric.journal.codes)
        if codes in metrics:
            metric.h_index = metrics[codes]['h_index']
            metric.impact_factor = metrics[codes]['impact_factor']
            metric.sjr_rank = metrics[codes]['sjr_rank']
            metric.sjr_quartile = metrics[codes]['sjr_quartile']
            metric.modified = now
            num_updated += 1
    models.JournalMetric.objects.bulk_update(
        to_update, fields=['h_index', 'impact_factor', 'sjr_rank', 'sjr_quartile', 'modified']
    )
    return {'created': len(to_create), 'updated': num_updated}


def update_publication_metrics(rate_limit=10):
    """
    Fetch and create/or update publication metrics for current year or a given year

    :param rate_limit: maximum number of requests per second
    :return: number of entries created or deleted
    """

    # fetch metrics for the year
    now = timezone.localtime(timezone.now())
    cr = CrossRef()
    oc = OpenCitations()

    last_month = now - timedelta(weeks=4)
    target_publications = models.Publication.objects.filter(code__regex=r'^10\.').filter(
        Q(metrics__isnull=True) | Q(metrics__modified__lte=last_month)
    )

    publications = target_publications.distinct('code').in_bulk(field_name='code')

    # Process at most CROSSREF_BATCH_SIZE publications at a time
    doi_list = list(publications.keys())
    to_create = []
    update_count = 0
    for doi in doi_list[:CROSSREF_BATCH_SIZE]:
        pub = publications.get(doi)
        citations = oc.citations(doi)
        mentions = cr.mentions(doi)
        to_update = models.ArticleMetric.objects.filter(publication=pub).distinct('year')
        entries = {item.year: item for item in to_update}
        for yr, count in mentions.items():
            citations[yr] = citations.get(str(yr), {'citations': 0, 'self_cites': 0})
            citations[yr]['mentions'] = count

        for yr, info in citations.items():
            if not yr:
                continue

            year = int(yr)
            if year in entries:
                metric = entries[year]
                metric.citations = info['citations']
                metric.self_cites = info['self_cites']
                metric.mentions = info.get('mentions', 0)
                metric.modified = now
                update_count += 1
            else:
                to_create.append(models.ArticleMetric(publication=pub, year=year, **info))

        # Update the publication modified date
        models.ArticleMetric.objects.bulk_update(
            entries.values(), fields=['citations', 'self_cites', 'mentions', 'modified']
        )
        time.sleep(1 / rate_limit)

    # Create new metrics entries
    if to_create:
        models.ArticleMetric.objects.bulk_create(to_create)

    return {'created': len(to_create), 'updated': update_count}


def get_thesis_kind(field) -> models.Publication.TYPES:
    """
    Determine the kind of thesis based on keywords in the field.
    :param field:
    :return:
    """
    if any(key in field.lower() for key in ['phd', 'ph.d.', 'doctor', 'dsc']):
        return models.Publication.TYPES.phd_thesis
    else:
        return models.Publication.TYPES.phd_thesis


def extract_date(field) -> str:
    """
    Extract a date from a field using a regex pattern.
    :param field: text
    :return:
    """
    date_pattern = re.compile(r'(\d{4}[-/]\d{2}[-/]\d{2})')
    match = date_pattern.search(field)
    if match:
        return match.group(1)
    return ''


SCHEMA_MAP = {
    'code': ('identifier', str),
    'title': ('name', str),
    'authors': ('creator', lambda authors: [a['name'] for a in authors if 'name' in a]),
    'editors': ('contributor', lambda editors: [e['name'] for e in editors if 'name' in e]),
    'kind': ('inSupportOf', get_thesis_kind),
    'publisher': ('publisher', lambda names: '; '.join(a['name'] for a in names)),
    'date': ('temporal', extract_date),
    'keywords': ('subject', list),
}

THESIS_META_MAP = {
    'code': ('identifier', str),
    'title': ('title', str),
    'authors': ('creator', lambda x: [x] if isinstance(x, str) else x),
    'kind': ('description', get_thesis_kind),
    'keywords': ('subject', list),
    'date': ('dateaccepted', extract_date),
}


def get_meta_key(name: str) -> str:
    """
    Extract a metadata key from a meta tag name
    :param name: The name of the meta tag
    """
    name = name.lower()
    key = name
    if name.startswith('dc.') or name.startswith('dcterms.'):
        key = name.split('.', 1)[-1]
    return key


def get_url_meta(url, extras=None) -> dict:
    """
    Get metadata from a URL
    :param url: The URL to fetch
    :param extras: additional properties to fetch name, value keyword pairs
    """
    extras = {} if not extras else extras
    r = requests.get(url)
    if r.status_code == requests.codes.ok:
        root = etree.parse(BytesIO(r.content), etree.HTMLParser())
        raw_info = [
                       (get_meta_key(el.get('name', 'junk')), el.get('content'))
                       for el in root.xpath('//meta')
                   ] + [
                       (value, el.text)
                       for prop, value in extras.items()
                       for el in root.xpath(f"//*[@{prop}='{value}']")
                   ]
        schema_info = defaultdict(list)
        for k, v in raw_info:
            schema_info[k].append(v)
        schema_info = {k: (v[0] if len(v) == 1 else v) for k, v in schema_info.items()}
        return schema_info

    return {}


def get_schema_meta(url: str) -> dict:
    """
    Fetch metadata from a URL using schema.org JSON-LD format
    :param url: url to fetch
    """
    r = requests.get(url)
    if r.status_code == requests.codes.ok:
        root = etree.parse(BytesIO(r.content), etree.HTMLParser())
        schema_info = root.xpath('//script[@type="application/ld+json"]')
        if schema_info:
            schema = json.loads(schema_info[0].text)
            pub_info = {
                field: converter(schema[k])
                for field, (k, converter) in SCHEMA_MAP.items()
                if k in schema
            }
            return pub_info
    return {}


def get_thesis_meta(url: str) -> dict:
    """
    Fetch thesis metadata from a URL using meta tags
    :param url: url to fetch
    """
    info = get_url_meta(url)
    if info:
        pub_info = {
            field: converter(info[k])
            for field, (k, converter) in THESIS_META_MAP.items()
            if k in info
        }
        return pub_info
    return {}


class Fetcher:
    """
    A class is a collection of class methods to fetch various publication related data.
    """

    @staticmethod
    def get_pdb():
        raise NotImplementedError("Subclasses should implement this method.")

    @staticmethod
    def get_doi(doi: str) -> dict:
        """
        Fetch publication metadata from CrossRef using a DOI.
        :param doi: Digital Object Identifier.
        """
        cr = CrossRef()
        results = cr.works(ids=[doi])

        # fix inconsistent json from works
        results = results if isinstance(results, list) else [results]

        # first pass to create publication details
        for item in results:
            record = ArticleParser(item['message'])
            entry = record.dict()
            return entry
        return {}

    @staticmethod
    def get_thesis(url: str) -> dict:
        """
        Fetch thesis metadata from a URL returns results of the first successful method
        :param url: url to fetch
        """
        for method in [get_schema_meta, get_thesis_meta]:
            info = method(url)
            if info:
                return {
                    'authors': info.get('authors', []),
                    'title': info.get('title', '').strip(),
                    'date': info.get('date', ''),
                    'kind': info.get('kind', models.Publication.TYPES.phd_thesis),
                    'keywords': info.get('keywords', []),
                    'code': info.get('code', url),
                    'editors': info.get('editors', []),
                    'publisher': info.get('publisher', ''),
                }
        return {}

    @staticmethod
    def get_patent(number: str) -> dict:
        number = number.replace(' ', '').upper()
        url = f'https://patents.google.com/patent/{number}'
        info = get_url_meta(url, extras={'itemprop': 'priorArtKeywords'})

        if info:
            return {
                'authors': info.get('contributor', []),
                'title': info.get('title', '').strip(),
                'date': info.get('date')[0] if isinstance(info.get('date'), list) else info.get('date', ''),
                'kind': models.Publication.TYPES.patent,
                'keywords': info.get('priorArtKeywords', []),
                'code': number,
            }
        return {}

    @staticmethod
    def get_book(isbn: str) -> dict:
        """
        Fetch book information by ISBN.
        :param isbn: ISBN number of the book.
        :return: BookParser object with book details.
        """
        return fetch_book([isbn])
