from io import BytesIO, StringIO
from collections import defaultdict
from datetime import date
import csv
import json
import os
import re
import requests
import subprocess
from lxml import etree, html
import itertools
from django.conf import settings
from django.utils import timezone

debug = False

KEYWORD_XPATH = {
    '10.1088': '/html/body/div[4]/div/div/div[1]/div[8]/dl/dd[2]/p',
    '10.1117': '/html/body//div[@class="header"]/a',
    '10.1149': '/html/body//a[@class="kwd-search"]',
    '10.1107': '/html/body/p[3]/b/a',
    '10.1016': '//*[@class="svKeywords"]',
}

PDB_FACILITIES = getattr(settings, 'PDB_FACILITIES', {})


def join_names(authors):
    return '; '.join(a['name'] for a in authors)


def join_strings(authors):
    if isinstance(authors, list):
        return '; '.join(authors)
    return authors


def get_thesis_kind(field):
    if any(key in field.lower() for key in ['phd', 'ph.d.', 'doctor', 'dsc']):
        return 'phd_thesis'
    elif any(key in field.lower() for key in ['msc', 'm.sc.', 'master']):
        return 'msc_thesis'
    else:
        return 'msc_thesis'


def get_meta_key(key):
    key = key.lower()
    if key.startswith('dc.') or key.startswith('dcterms.'):
        key = key.split('.', 1)[-1]
    return key


def extract_date(field):
    date_pattern = re.compile(r'(\d{4}[-/]\d{2}[-/]\d{2})')
    match = date_pattern.search(field)
    if match:
        return match.group(1)


SCHEMA_MAP = {
    'code': ('identifier', str),
    'title': ('name', str),
    'authors': ('creator', join_strings),
    'editor': ('contributor', join_names),
    'kind': ('inSupportOf', get_thesis_kind),
    'publisher': ('publisher', join_names),
    'date': ('temporal', extract_date),
}


THESIS_META_MAP = {
    'code': ('identifier', str),
    'title': ('title', str),
    'authors': ('creator', join_strings),
    'editor': ('contributor', join_strings),
    'kind': ('description', get_thesis_kind),
    'publisher': ('publisher', join_strings),
    'keywords': ('subject', join_strings),
    'date': ('dateaccepted', extract_date),
}


def fetch_pdbs():
    biosync_urls = {
        f'https://biosync.sbkb.org/biosync_pdbtext/pdbtext{pdb_name}.txt': facilities
        for pdb_name, facilities in PDB_FACILITIES.items()
    }
    pdb_data = {}
    for url, facilities in biosync_urls.items():
        r = requests.get(url)
        if r.status_code == requests.codes.ok:
            csvfile = StringIO(r.text)
            dialect = csv.Sniffer().sniff(csvfile.read(4024))
            csvfile.seek(0)
            reader = csv.DictReader(csvfile, dialect=dialect)
            for row in reader:
                code = row['PDB_ID'].lower().strip()
                row['PDB_ID'] = code
                if code in pdb_data:
                    pdb_data[code]['BEAMLINES'].extend(facilities)
                else:
                    row['BEAMLINES'] = facilities
                    pdb_data[code] = row
                add_pdb_entry(row)


def add_pdb_entry(p):
    from beamlines.models import Facility
    from .models import PDBDeposition, Publication, Article

    existing = PDBDeposition.objects.filter(code__iexact=p['PDB_ID'])
    if existing.count():
        create_new = False
        b = existing[0]
        if b.reference:
            return
    else:
        create_new = True

    info = get_raw_pdb_info(p['PDB_ID'])
    doi = info.pop('reference')[0]
    bls = [bl for bl in Facility.objects.filter(acronym__in=[k.upper() for k in p['BEAMLINES']])]
    reference_id = None
    if doi:
        pubs = Article.objects.filter(code__icontains=doi)
        if pubs.count() == 1:
            reference_id = pubs[0].pk
            pubs[0].beamlines.add(*bls)
        else:
            pub = auto_add_pub(doi, comment="Added automatically on {0}".format(date.today().isoformat()),
                               beamlines=bls, affiliation=info['affiliation'])
            reference_id = pub.pk
    else:
        pubs = Publication.objects.filter(title__icontains=info['title'].strip()[5:-5])
        if pubs.count() == 1:
            reference_id = pubs[0].pk
        else:
            info['notes'] = 'Could not find published article automatically'

    info['reference_id'] = reference_id
    if create_new:
        b = PDBDeposition.objects.create(**info)
    else:
        b.reference_id = reference_id
        b.save()
    b.beamlines.add(*bls)


def get_raw_pdb_info(code):
    details = get_pdb_meta(code.lower())
    doi, pmid = details.get('reference', ("", ""))
    doi, pmid = doi.strip(), pmid.strip()
    affiliation = {}

    info = {
        'reference': (doi, pmid),
        'authors': details.pop('authors'),
        'title': details.pop('title'),
        'date': details.pop('date'),
        'affiliation': affiliation,
        'kind': 'pdb',
        'code': code.lower(),
        'category': 'beamline',
        'keywords': details.pop('keywords'),
        'history': ['Added from BioSync on {0}'.format(date.today().isoformat())],
        'details': details,
    }
    return info


def update_pdb_info(p):
    from . import models
    info = get_raw_pdb_info(p.code)
    reference = info.pop('reference')
    info['modified'] = timezone.localtime(timezone.now())
    if reference:
        ref_pub = models.Article.objects.filter(code=reference[0]).first()
        if ref_pub:
            info['reference'] = ref_pub
    models.PDBDeposition.objects.filter(pk=p.pk).update(**info)
    if p.reference and not p.reference.affiliation:
        a = p.reference
        a.affiliation = info['affiliation']
        a.save()


def auto_add_pub(doi, comment="", beamlines=[], affiliation=None):
    from . import models
    bs = models.Article.objects.filter(code__icontains=doi)
    if bs.count():
        return bs[0]
    info = get_pub(doi)
    if not info['affiliation']:
        info['affiliation'] = affiliation
    if comment:
        info.update(history=[comment])
    for issn in info.get('journal', {}).get('issn', '').split(';'):
        js = models.Journal.objects.filter(issn__icontains=issn)
        if js.count():
            journal = js[0]
            info['journal_id'] = journal.pk
            break
    if 'journal' in info and not 'journal_id' in info:
        journal = models.Journal.objects.create(**info['journal'])
        info['journal_id'] = journal.pk

    info.pop('journal')
    funders = info.pop('funders', [])
    info.pop('unknown_funders', None)

    if beamlines:
        info['category'] = models.Publication.CATEGORIES.beamline
    obj = models.Article.objects.create(**info)

    if beamlines:
        obj.beamlines.add(*beamlines)
    if funders:
        prep_funders = []
        for f in funders:
            fs = models.FundingSource.objects.filter(doi=f['doi'])
            if fs.count():
                prep_funders.append(fs[0])
            else:
                prep_funders.append(f)
        funders = [f if isinstance(f, models.FundingSource) else models.FundingSource.objects.create(**f) for f in
                   prep_funders]
        obj.funders.add(*funders)

    return obj


def get_pdb_meta(pdbcode):
    r = requests.get('https://www.rcsb.org/pdb/files/{0}.cif?headerOnly=YES'.format(pdbcode.upper()))
    if r.status_code == requests.codes.ok:
        data = r.text
        loops = re.findall(r'\nloop_([^#]+)\n#', data, re.DOTALL | re.MULTILINE)
        new_data = re.sub(r'(\nloop_[^#]+\n#)', '', data)
        info = _flat_dict(new_data)
        for loop in loops:
            key, subinfo = _parse_loop(loop)
            info[key] = subinfo

        kwrds = info['struct_keywords'].get('text', '').split(', ') + info['struct_keywords'].get('pdbx_keywords',
                                                                                                  '').split(', ')
        kwrds = {v.lower().strip() for v in kwrds}
        for k in ['pdbx_entity_nonpoly', 'citation_author', 'citation']:
            if not k in info:
                info[k] = []
            if isinstance(info[k], dict):
                info[k] = [info[k]]
        if len(info['citation']):
            reference = (info['citation'][0].get('pdbx_database_id_DOI', '').replace('?', ''),
                         info['citation'][0].get('pdbx_database_id_PubMed', '').replace('?', ''))
        else:
            reference = ("", "")
        details = {
            'title': ". ".join(v['title'] for v in info['citation']),
            'subtitle': info['struct']['title'],
            'reference': reference,
            'date': (
                info['database_PDB_rev']['date']
                if not isinstance(info['database_PDB_rev'], list)
                else info['database_PDB_rev'][0]['date']
            ),
            'authors': [v['name'] for v in info.get('citation_author', [])],
            'keywords': "; ".join(kwrds),
            'description': info['struct'].get('pdbx_descriptor', ''),
            'polymer': len(info['pdbx_poly_seq_scheme']),
            'components': [v['name'].title() for v in info.get('pdbx_entity_nonpoly', [])],
        }
        return details


def get_book(isbn):
    if not isinstance(isbn, list):
        isbns = [isbn]
    else:
        isbns = isbn

    for isbn in isbns:
        isbn = re.sub(r'[\s_-]', '', isbn)
        url = "https://www.googleapis.com/books/v1/volumes?q=isbn:{0}".format(isbn)
        r = requests.get(url)
        if r.status_code == requests.codes.ok:
            record = r.json()
            if debug:
                import pprint
                pprint.pprint(record)
            if record['totalItems'] == 0:
                continue
            record = record['items'][0]['volumeInfo']
            _auth = []
            isbn_list = [i.get('identifier', None) for i in record.get('industryIdentifiers', [{}]) if
                         len(i.get('identifier', '')) == 13]
            isbn = isbn_list[0] if len(isbn_list) > 0 else isbn
            info = {
                'isbn': isbn,
                'main_title': record['title'] + (
                    "" if not record.get('subtitle') else ": {0}".format(record['subtitle'])),
                'editor': '; '.join(record.get('authors', [])),
                'publisher': record.get('publisher', ''),
                'kind': 'chapter',
                'date': '{0}-01-01'.format(record['publishedDate']) if len(
                    record.get('publishedDate', '')) == 4 else record.get('publishedDate', ''),
                'keywords': '; '.join(record.get('categories', [])),
            }
            if len(info['date']) == 7:
                info['date'] = '{0}-01'.format(info['date'])
            return info


def get_patent(number):
    number = number.replace(' ', '').replace('/', '').upper()
    r = requests.get('https://www.google.com/patents/{0}.enw'.format(number))
    if r.status_code == requests.codes.ok:
        dat = enw(f"{r.text}")

    pp = {
        'authors': dat.get('A', '').split(';'),
        'title': dat.get('T', ''),
        'date': f'{dat["D"]}-01-01',
        'kind': "patent",
        'reviewed': False,
        'keywords': dat.get('K', ''),
        'category': None,
        'number': number,
    }
    return pp


def get_resource_meta(doi, resource="works", debug=False):
    url = 'https://api.crossref.org/{1}/{0}'.format(doi, resource)
    r = requests.get(url)

    if r.status_code == requests.codes.ok:
        record = r.json()
        return record['message']


TYPEDB = {
    'j': 'journal',
    'p': 'proceedings',
    'd': 'magazine',
    'k': 'bookseries',
    'b': 'book',
}

WORKS_TYPES = {
    'reference-book': 'chapter',
    'proceedings-article': 'proceeding',
    'dissertation': 'msc_thesis',
    'edited-book': 'chapter',
    'journal-article': 'article',
    'report': 'chapter',
    'book-track': 'chapter',
    'standard': 'chapter',
    'book-section': 'chapter',
    'book-part': 'chapter',
    'book': 'chapter',
    'book-chapter': 'chapter',
    'monograph': 'chapter',
}


def _prep_issn(issn_list):
    return list(sorted([v.replace('-', '').strip() for v in issn_list]))


def get_journal(issn):
    if isinstance(issn, list):
        issns = issn
    else:
        issns = [issn]
    jinfo = {'issn': _prep_issn(issns), 'sjr': 0, 'hindex': 0, 'ifactor': 0}
    for code in issns:
        r = requests.get('https://api.crossref.org/journals/{0}-{1}'.format(code[:4], code[-4:]))
        if r.status_code == requests.codes.ok:
            record = r.json()
            jinfo.update({
                'issn': _prep_issn(record['message']['ISSN']),
                'title': record['message']['title'],
                'publisher': record['message']['publisher']})
            break

    for code in jinfo['issn']:
        if code in SJRDB:
            jinfo.update({
                'sjr': SJRDB[code]['SJR'],
                'ifactor': SJRDB[code]['Cites / Doc. (2years)'] if jinfo['ifactor'] == 0 else jinfo['ifactor'],
                'hindex': int(SJRDB[code]['H index']),
                'score_date': date.today()})
            jinfo['kind'] = TYPEDB.get(SJRDB[code]['Type'])
            jinfo['issn'] = jinfo['issn'] + [SJRDB[code]['ISSN']]
            if not 'title' in jinfo:
                jinfo.update(title=SJRDB[code]['Title'])

        if code in IFDB:
            jinfo.update({'ifactor': IFDB[code][sorted(IFDB[code].keys())[-4]]})
        if 'score_date' in jinfo:
            break

    if not 'title' in jinfo:
        url = 'https://xissn.worldcat.org/webservices/xid/issn/{0}-{1}'.format(issn[:4], issn[-4:])
        params = {'method': 'getMetadata', 'format': 'json'}
        r = requests.get(url, params=params)
        if r.status_code == requests.codes.ok:
            record = r.json()
            try:
                record = record['group'][0]['list'][0]
                jinfo.update({
                    'issn': [record['issn'].replace('-', '')],
                    'title': record['title'],
                    'publisher': record['publisher']})
            except:
                pass
    if 'issn' in jinfo:
        jinfo['issn'] = ';'.join(sorted(set([v for v in jinfo['issn'] if v])))
        return jinfo


def get_sjr_issn(issn):
    url = 'https://www.scimagojr.com/journalsearch.php?q={0}&tip=issn'.format(issn)
    text = subprocess.check_output(['links', "-width", "512", "-dump", url])
    issns = re.findall(r'ISSN:\s+((?:[\dA-Z]{8},? ?)*)', text)
    return [i.strip() for i in issns[0].split(',')]


def get_citedby(doi, user='michel.fodje@lightsource.ca'):
    url = 'https://www.crossref.org/openurl/'
    params = {
        'pid': user,
        'id': 'doi:{0}'.format(doi),
        'noredirect': 'true'
    }
    r = requests.get(url, params=params)
    if r.status_code == requests.codes.ok:
        try:
            root = etree.parse(BytesIO(r.content)).getroot()
            query = root[0][1][0]
            count = int(query.get('fl_count'))
            # print 'Citations found for doi', doi, u'[#{0}]'.format(count)
            return count
        except:
            # print u'ERROR fetching citations for doi', doi
            return 0
    else:
        # print u'ERROR fetching citations for doi', doi, u'CODE [{0}]'.format(requests.codes.ok)
        return 0


def _load_if():
    pgs = ['0-A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U',
           'V', 'W', 'X', 'Y', 'Z']
    fname = os.path.join(os.path.dirname(__file__), "testing", "IF-DATA", "journal-impact-factor-list-2014_{0}.html")
    headers = ['index', 'title', 'issn', '2014', '2012', '2011', '2010', '2009', '2008']
    ftypes = ['2014', '2012', '2011', '2010', '2009', '2008']
    IF_DB = {}
    for pg in pgs:
        with open(fname.format(pg), 'rb') as fobj:
            root = etree.parse(fobj, etree.HTMLParser())
            data = root.xpath('/html/body/div[2]/div/div[2]/div/div[2]/table//tr')
            for jn in data:
                values = [el.text for el in jn.xpath('td')]
                if not any(values): continue
                jndict = dict(list(zip(headers, values)))
                for k in ftypes:
                    if jndict[k] not in ['-', '', None]:
                        jndict[k] = float(jndict[k].strip())
                    else:
                        jndict[k] = 0.0
                jnkey = jndict['issn'].replace('-', '').strip()
                IF_DB[jnkey] = jndict
    with open('impact-factors.json', 'w') as outf:
        json.dump(IF_DB, outf, indent=4)

    return IF_DB


def _fetch_sjr(year):
    url = f'https://www.scimagojr.com/journalrank.php?category=0&area=0&year={year}&country=&order=sjr&page=0&min=0&min_type=cd&out=xls'
    return requests.get(url)


def _parse_sjr(r):
    import xlrd
    book = xlrd.open_workbook(file_contents=r.content)
    sheet = book.sheet_by_index(0)
    headers = dict((i, sheet.cell_value(0, i)) for i in range(sheet.ncols))
    raw = (dict((headers[j], sheet.cell_value(i, j)) for j in headers) for i in range(1, sheet.nrows))
    data = {}
    for row in raw:
        if row.get('ISSN'):
            k = row['ISSN'].split()[-1]
            row['ISSN'] = k
            data[k] = row
        else:
            k = row['Title']
            data[k] = row
    return data


def get_sjr(year):
    r = _fetch_sjr(year)
    return _parse_sjr(r)


def load_csv(fname, pub_type=None):
    with open(fname, 'rb') as csvfile:
        dialect = csv.Sniffer().sniff(csvfile.read(4024))
        csvfile.seek(0)
        reader = csv.DictReader(csvfile, dialect=dialect)
        if not pub_type:
            data = [row for row in reader]
        else:
            data = [row for row in reader if row['Publication_Type'] == pub_type]
    return data


def search_pub(title, debug=False):
    url = 'https://search.crossref.org/dois?q={0}&rows=10&sort=score'.format(title)
    r = requests.get(url)
    if r.status_code == requests.codes.ok:
        record = r.json()[0]
        record['doi'] = record['doi'].replace('https://dx.doi.org/', '')
        record.pop('coins')
        return record


def enw(data):
    raw = defaultdict(list)
    for k, v in re.findall(r'%(\w)\s(.+)\n', data):
        raw[k].append(re.sub(r'\u2010', r'-', v.strip()))
    nraw = {k: (v[0] if len(v) == 1 else '; '.join(v)) for k, v in list(raw.items())}
    return nraw


def enw2json(data):
    raw = defaultdict(list)
    data = re.sub(r'(%\w\s)', r'\n\1', re.sub(r'\n\s+', r' ', data))
    for k, v in re.findall(r'%(\w)\s(.+)\n', data):
        raw[k].append(re.sub('\u2010', r'-', v.strip()))
    nraw = {k: (v[0] if len(v) == 1 else '; '.join(v)) for k, v in list(raw.items())}
    info = {
        'DOI': nraw.get('R', '').replace('doi:https://dx.doi.org/', ''),
        'author': [{'family': k.split(', ')[0], 'given': k.split(', ')[1]} for k in raw['A']],
        'title': nraw.get('T', ''),
        'container-title': [nraw.get('J', '')],
        'volume': nraw['V'],
        'issue': nraw.get('N'),
        'page': nraw['P'],
        'subject': raw['K'],
        'issued': {'date-parts': [nraw['D'].split('-')]},
        'type': '-'.join(nraw.get('0', '').lower().split()),
        'publisher': 'AIP'
    }
    return info


def get_aip(doi):
    r = requests.get('https://scitation.aip.org/content/aip/proceeding/aipcp/{0}/cite/endnote'.format(doi))
    try:
        info = enw2json(f"{r.text}")
        return info
    except:
        return {}


def get_doi_meta(doi):
    r = requests.get('https://dx.doi.org/{0}'.format(doi))
    if r.status_code == requests.codes.ok:
        root = html.parse(r.content.decode('utf-8'))
        raw_info = defaultdict(list)
        for e in root.xpath('/html//meta'):
            print(e.text_content(), [list(e.keys()), list(e.values())])
            raw_info[e['name']].append(e['content'])
        info = {k: (v[0] if len(v) == 1 else v) for k, v in raw_info}
        return info


def get_schema_meta(url):
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


def get_thesis_meta(uri):
    r = requests.get(uri)
    root = etree.parse(BytesIO(r.content), etree.HTMLParser())
    raw_info = [(get_meta_key(el.get('name', 'junk')), el.get('content')) for el in root.xpath('//meta')]
    schema_info = defaultdict(list)
    for k, v in raw_info:
        schema_info[k].append(v)
    schema_info = {k: (v[0] if len(v) == 1 else v) for k, v in schema_info.items()}
    if schema_info:
        pub_info = {
            field: converter(schema_info[k])
            for field, (k, converter) in THESIS_META_MAP.items()
            if k in schema_info
        }
        return pub_info
    return {}


SUPPORTED_THESIS_METHODS = [get_schema_meta, get_thesis_meta]


def get_thesis(url):
    for method in SUPPORTED_THESIS_METHODS:
        info = method(url)
        if info:
            return info


def get_pub(doi, debug=False):
    if not doi:
        return

    url = f'https://api.crossref.org/works/{doi}'
    r = requests.get(url)
    good = (r.status_code == requests.codes.ok)
    if not good and re.match(r'10.1063/\d\.\d+', doi):
        record = get_aip(doi)
        if record:
            good = True
    else:
        record = r.json()['message']

    if good:
        try:
            date_parts = list(map(int, record['issued']['date-parts'][0] + [1, 1, 1]))
        except:
            date_parts = list(map(int, record['deposited']['date-parts'][0] + [1, 1, 1]))
        if not record['container-title'] and re.match(r'10.1063/\d\.\d+', doi):
            record.update(get_aip(doi))

        # prepare affiliations
        _affil = [[n['name'] for n in a.get('affiliation', [])] for a in record.get('author', [])]
        _institutions = list(sorted({n for n in itertools.chain(*_affil)}))
        affiliation = None
        if _institutions:
            affiliation = {
                'institutions': _institutions,
                'authors': [[_institutions.index(name) for name in names] for names in _affil],
            }
        pub_dict = {
            'authors': [n['family'] + ', ' + n.get('given', '') for n in record.get('author', [])],
            'affiliation': affiliation,
            'title': ': '.join([t.strip() for t in record['title']]) if isinstance(record['title'], list) else record[
                'title'].strip(),
            'keywords': re.sub(r'\(([^()]+)\)', r'', '; '.join(record.get('subject', []))),
            'kind': WORKS_TYPES[record['type']],
            'reviewed': False,
            'volume': record.get('volume'),
            'number': record.get('issue'),
            'pages': record.get('page'),
            'code': record['DOI'],
            'date': date(*date_parts[:3]).isoformat(),
        }

        if 'funder' in record:
            pub_dict['funders'] = [get_funder(v['DOI']) for v in record['funder'] if v.get('DOI')]
            pub_dict['unknown_funders'] = [{'name': v['name']} for v in record['funder'] if not v.get('DOI')]

        if record.get('ISSN'):
            issn = record.get('ISSN')[0] if isinstance(record.get('ISSN')[0], list) else record.get('ISSN')
            issn = _prep_issn(issn)
            pub_dict['journal'] = get_journal(issn)
            pub_dict['kind'] = 'proceeding' if WORKS_TYPES[record['type']] == 'proceeding' else 'article'
        elif record.get('ISBN'):
            isbns = [v.split('/')[-1] for v in record['ISBN']]
            pub_dict['book'] = get_book(isbns)
            pub_dict['kind'] = 'proceeding' if WORKS_TYPES[record['type']] == 'proceeding' else 'chapter'
        else:
            if record.get('container-title'):
                pub_dict['book'] = {
                    'title': record['container-title'][0] if isinstance(record['container-title'], list) else record[
                        'container-title'].strip(),
                    'kind': 'book',
                }
        pub_dict['title'] = re.sub(r'\$_?{?(?:\\bf)\s*([^$]*)}\$', r'\1', pub_dict['title'])
        return pub_dict


def get_funder(doi):
    record = get_resource_meta(doi, resource="funders")
    if record:
        return {
            'name': record['name'],
            'location': record['location'],
            'doi': '10.13039/{0}'.format(record['id']),
            'acronym': min((record['alt-names'] + [record['name']]), key=len),
        }


class DotExpandedDict(dict):
    """
    A special dictionary constructor that takes a dictionary in which the keys
    may contain dots to specify inner dictionaries. It's confusing, but this
    example should make sense.

    >>> d = DotExpandedDict({'person.1.firstname': ['Simon'], \
    'person.1.lastname': ['Willison'], \
    'person.2.firstname': ['Adrian'], \
    'person.2.lastname': ['Holovaty']})
    >>> d
    {'person': {'1': {'lastname': ['Willison'], 'firstname': ['Simon']}, '2': {'lastname': ['Holovaty'], 'firstname': ['Adrian']}}}
    >>> d['person']
    {'1': {'lastname': ['Willison'], 'firstname': ['Simon']}, '2': {'lastname': ['Holovaty'], 'firstname': ['Adrian']}}
    >>> d['person']['1']
    {'lastname': ['Willison'], 'firstname': ['Simon']}

    # Gotcha: Results are unpredictable if the dots are "uneven":
    >>> DotExpandedDict({'c.1': 2, 'c.2': 3, 'c': 1})
    {'c': 1}
    """

    def __init__(self, key_to_list_mapping):
        super().__init__()
        for k, v in list(key_to_list_mapping.items()):
            current = self
            bits = k.split('.')
            for bit in bits[:-1]:
                current = current.setdefault(bit, {})
            # Now assign value to current position
            try:
                current[bits[-1]] = v
            except TypeError:  # Special-case if current isn't a dict.
                current = {bits[-1]: v}


def _flat_dict(text):
    m = re.findall(rf'^_([\w\.]+)[\s\n]+([^_#]+)', text, re.DOTALL | re.MULTILINE)
    d = dict([(v[0], re.sub(r"'(.*)'", r'\1', re.sub(r'(^;?)|(\n;?)', ' ', v[1], re.MULTILINE).strip())) for v in m])
    return DotExpandedDict(d)
    # return d


def _parse_loop(text):
    keys = re.findall(r'\n_([\w\.]+)', text)
    prefix = os.path.commonprefix(keys)
    ikeys = [v.split(prefix)[-1] for v in keys]

    text = re.sub(r'\n(_[\w\.]+)', '', text)
    vre = r"((?:[^\s\']+)|(?:'[^\'\n]+'))\s+"
    patt = r"^" + vre * len(keys) + r"$"
    vals = re.findall(patt, text, re.DOTALL | re.MULTILINE)
    return prefix[:-1], [dict(list(zip(ikeys, [re.sub(r"'(.*)'", r'\1', item.strip()) for item in val]))) for val in vals]


# Find and load publication metrics
DB_FILES = {}
SJRDB = {}
IFDB = {}


def load_metrics():
    global SJRDB, IFDB
    for db in ['sjr', 'impact-factors']:
        for path in [os.path.join(settings.LOCAL_DIR, 'metrics'), os.path.join(os.path.dirname(__file__), 'data')]:
            db_file = os.path.join(path, '{0}.json'.format(db))
            if os.path.exists(db_file):
                DB_FILES[db] = db_file
                break
    if 'sjr' in DB_FILES:
        with open(DB_FILES['sjr'], 'r') as f:
            SJRDB = json.load(f)
    if 'impact-factors' in DB_FILES:
        with open(DB_FILES['impact-factors'], 'r') as f:
            IFDB = json.load(f)


# load publication metrics
load_metrics()
