#!/usr/bin/env python3

import argparse
import os
import random
import shutil
from collections import defaultdict
from pathlib import Path

import yaml
from faker import Faker
from unidecode import unidecode

# This script is used to generate fake data for the Bespoke system. some external data is used to generate the data
# such as sample photos, universities, country names, and sample types. The data is saved in YAML format

PHOTOS_DIR = Path("~/Stuff/data-gen/avatars")       # Path photos dir, names should be numbers,
                                                    # 0.webp, 1.webp, etc Odd for female even for male
DATA_DIR = Path(__file__).parent / 'data'

SUBJECTS = [1, 2, 3, 4, 5, 6, 7]
HAZARD_TYPES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15]
HAZARDS = [
    2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30,
    31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57,
    58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74
]
STAGES = {
    1: 1,
    2: 3
}

TRACKS = {
    1: 'GA',
    2: 'RA',
    3: 'PA'
}
CLASSIFICATIONS = [
    'undergraduate', 'masters', 'doctorate', 'postdoc', 'faculty', 'professional', 'faculty', 'faculty', 'faculty'
]
TITLES = {
    'male': ['Prof', 'Mr', 'Dr', 'Sir'],
    'female': ['Prof', 'Ms', 'Dr'],
}
SAMPLE_TYPES = [
    'chemical', 'macromolecule', 'geologic', 'human_tissue', 'animal_tissue', 'plant', 'microbe', 'other'
]
DEPARTMENTS = [
    'Medicine & Dentistry',
    'Biological Sciences',
    'Veterinary Science',
    'Agriculture',
    'Physical Sciences',
    'Mathematical Sciences',
    'Computer Science',
    'Engineering & Technology',
    'Architecture, Building & Planning',
    'Social Studies',
    'Law',
    'Business & Administrative Studies',
    'Mass Communications & Documentation',
    'Languages',
    'Historical & Philosophical Studies',
    'Creative Arts & Design',
    'Education'
]

with open(DATA_DIR / 'universities.yml', 'r') as file:
    UNIVERSITIES = yaml.safe_load(file)

with open(DATA_DIR / 'country-names.yml', 'r') as file:
    NAMES = yaml.safe_load(file)

with open(DATA_DIR / 'samples.yml', 'r') as file:
    SAMPLES = yaml.safe_load(file)

print('Loaded all databases ...')

EQUATIONS = [
    r'$$ y = mx + b $$',
    r'$$ y = \frac{1}{1 + e^{-x}} $$',
    r'$$ y = \frac{1}{1 + e^{-k(x - x_0)}} $$',
    r'$$ x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a} $$',
    r'$$ e^{i\pi} + 1 = 0 $$',
    r'$$ \int_\Lambda A(a,\lambda)B(b,\lambda) \rho(\lambda)d\lambda $$'
    r'$$ \int_{0}^{\infty} e^{-x^2} \,dx = \frac{\sqrt{\pi}}{2} $$'
    r'$$ \sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6} $$'
]
PHOTOS_DIR = PHOTOS_DIR.expanduser().resolve()
NUM_PHOTOS = len(list(PHOTOS_DIR.glob('*.webp')))

ROLES = [
    "admin:uso", "staff:contracts", "curator:publications", "staff:hse", "manager:science", "safety-approver",
    "equipment-reviewer",
]
TECHNIQUES = {
    1: {'name': 'Photo Emission/Electron Spectroscopy', 'acronym': 'PES', 'techniques': [1, 2, 3]},
    4: {'name': 'X-ray Absorption Spectroscopy', 'acronym': 'XAS', 'techniques': [7, 4, 5, 6]},
    9: {'name': 'Fourier Transform Infrared Spectroscopy', 'acronym': 'FTIR', 'techniques': [8, 9, 20]},
    11: {'name': 'X-ray Magnetic Dichroism', 'acronym': 'XMD', 'techniques': [11, 12, 13]},
    14: {'name': 'Resonant X-ray Scattering', 'acronym': 'RXS', 'techniques': [14, 15]},
    16: {'name': 'X-ray Emission Spectroscopy', 'acronym': 'XES', 'techniques': [10, 16, 17]},
    19: {'name': 'X-ray fluorescence microscopy', 'acronym': 'XFM', 'techniques': [19, 18]},
    22: {'name': 'X-ray Tomography', 'acronym': 'XT', 'techniques': [22, 23, 24]},
    27: {'name': 'Scanning Transmission X-ray Microscopy', 'acronym': 'STXM', 'techniques': [27, 28, 21]},
    29: {'name': 'Small-Angle X-Ray Scattering', 'acronym': 'SAXS', 'techniques': [29, 30, 31]},
    32: {'name': 'X-ray Diffraction', 'acronym': 'XRD', 'techniques': [32, 36, 25, 26]},
    34: {'name': 'Macromolecular Crystallography', 'acronym': 'MX', 'techniques': [33, 34, 37]},
    38: {'name': 'X-ray Lithography', 'acronym': 'LIGA', 'techniques': [38]},
}

STATES = [
    'operating', 'operating', 'operating', 'operating',
]
SAMPLE_STATES = ['solid', 'liquid', 'gas', 'frozen', 'suspension', 'crystal']
SAMPLE_UNITS = {
    'solid': 'g',
    'liquid': 'mL',
    'gas': 'L',
    'frozen': 'g',
    'suspension': 'mL',
    'crystal': 'ug',
}

fake = Faker()


def fake_first_name_female(country):
    if country in NAMES['female']:
        return random.choice(NAMES['female'][country])
    else:
        return fake.first_name_female()


def fake_first_name_male(country):
    if country in NAMES['male']:
        return random.choice(NAMES['male'][country])
    else:
        return fake.first_name_female()


def fake_last_name(country):
    if country in NAMES['last']:
        return random.choice(NAMES['last'][country])
    else:
        return fake.last_name()


def first_char(text):
    text = text.strip()
    return '' if not text else text[0]


def make_acronym(name):
    return (''.join(w[0] for w in name.strip().split())).upper()


class FakeUser:

    def __init__(self, name='data', facilities=None):
        self.fake = Faker()
        self.name = name
        # update admin fields
        self.new_users = []
        self.new_institutions = {
            'Bespoke Facility': {
                'model': 'users.institution',
                'pk': 1,
                'fields': {
                    'created': '2024-12-30 20:49:59.049236+00:00',
                    'modified': '2024-12-30 20:49:59.049236+00:00',
                    'name': 'Bespoke Facility',
                    'location': f"Areion Prime, Valles District, The Martian Confederation",
                    'sector': 'academic',
                    'domains': f"<@bespoke.com>",
                    'state': 'exempt',
                }
            }
        }
        self.new_reviewers = []
        self.new_addresses = []

        self.user_count = 1
        self.reviewer_count = 1
        self.institution_count = 1
        self.address_count = 1

        self.user_names = defaultdict(int)
        self.facility_acronyms = {} if not facilities else facilities

        path = Path(name)
        self.data_path = path / 'kickstart' / '001-users.yml'
        self.photo_path = path / 'media' / 'photo'

        self.photo_path.mkdir(parents=True, exist_ok=True)
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.save_photo('admin')  # make sure admin account has a photo also

    def make_username(self, first_name, last_name, other_name=''):
        username = unidecode(f'{first_name}{first_char(last_name)}{first_char(other_name)}'.lower())
        self.user_names[username] += 1
        if self.user_names[username] > 1:
            return f'{username}{self.user_names[username]}'
        return username

    def add_address(self, info):
        pk = self.address_count
        self.new_addresses.append({
            'model': 'users.address',
            'pk': pk,
            'fields': {
                'created': '2024-12-30 20:49:59.049236+00:00',
                'modified': '2024-12-30 20:49:59.049236+00:00',
                'address_1': info['department'],
                'address_2': f"{info['address']}",
                'city': info['city'],
                'region': info['state'],
                'postal_code': info['zip'],
                'country': info['country'],
                'phone': info['phone'],
            }
        })

        self.address_count += 1
        return pk

    def add_reviewer(self, user, fields):
        subject_areas = list(set(fields + random.sample(SUBJECTS, random.randint(3, 7))))
        techniques = []
        for tech in random.sample(list(TECHNIQUES.keys()), random.randint(3, 5)):
            techniques.extend(TECHNIQUES[tech]['techniques'])
        pk = self.reviewer_count
        self.new_reviewers.append({
            'model': 'proposals.reviewer',
            'pk': pk,
            'fields': {
                'created': '2024-12-30 20:49:59.049236+00:00',
                'modified': '2024-12-30 20:49:59.049236+00:00',
                'user': user,
                'active': True,
                'techniques': techniques,
                'areas': subject_areas,
            }
        })
        self.reviewer_count += 1
        return pk

    def add_institution(self, info):
        name = info['institution']
        entry = {
            'model': 'users.institution',
            'pk': self.institution_count + 1,
            'fields': {
                'created': '2024-12-30 20:49:59.049236+00:00',
                'modified': '2024-12-30 20:49:59.049236+00:00',
                'name': info['institution'],
                'location': f"{info['city']}, {info['state']}, {info['country']}",
                'sector': 'academic',
                'domains': f"<{info['domain']}>",
                'state': random.choice(['pending', 'active', 'active', 'active']),
            }
        }
        if name not in self.new_institutions:
            self.new_institutions[name] = entry
            self.institution_count += 1

        return self.new_institutions[name]

    def make_random_info(self):
        self.user_count += 1
        kind = {0: 'male', 1: 'female'}.get(self.user_count % 2)

        is_staff = random.randint(0, 100) < 4  # 4% chance of being staff
        if is_staff:
            domain = '@bespoke.com'
            institution = 'Bespoke Facility'
            country = 'Martian Confederation'
            city = 'Areion Prime'
            state = 'Valles District'
            address = '1 Synchrotron Way'
            department = 'Beamline Operations'
            zip_code = 'AP00-M0001'
            roles = '<staff>'
            classification = 'professional'
            fac = random.choice(list(self.facility_acronyms.values()))
            if random.choice([True, False]):
                roles += f'<staff:{fac.lower()}>'
                if random.choice([True, False]):
                    roles += f'<admin:{fac.lower()}><reviewer:{fac.lower()}>'
                elif random.choice([True, False]):
                    roles += f'<reviewer:{fac.lower()}>'
            elif random.choice([True, True, False]):
                roles += '<{}>'.format(random.choice(ROLES))
            if kind == 'male':
                first_name = fake_first_name_male("Canada")
            else:
                first_name = fake_first_name_female("Canada")
            last_name = fake_last_name("Canada")
        else:
            inst_info = random.choice(UNIVERSITIES)
            institution = inst_info['university']
            domain = f"@{inst_info['domain']}"
            roles = '<user>'
            country = inst_info['country']
            city = inst_info['city']
            full_address = inst_info['address'].split(', ')
            state = full_address[-1]
            address = ', '.join(full_address[:-1])
            department = random.choice(DEPARTMENTS)
            zip_code = self.fake.postalcode()
            classification = random.choice(CLASSIFICATIONS)

            if kind == 'male':
                first_name = fake_first_name_male(country)
            else:
                first_name = fake_first_name_female(country)
            last_name = fake_last_name(country)
        other_name = ''
        if random.randint(0, 100) < 10:
            other_name = self.fake.name_nonbinary()
        username = self.make_username(first_name, last_name, other_name)
        fields = random.sample(SUBJECTS, random.randint(2, 4))
        phone = self.fake.phone_number()[:20]
        email = unidecode(f'{first_name}.{last_name}{domain}').replace(' ', '').lower()
        return {
            'country': country,
            'city': city,
            'state': state,
            'address': address,
            'year': random.randint(2010, 2024),
            'month': random.randint(1, 12),
            'zip': zip_code,
            'phone': phone,
            'department': department,
            'institution': institution,
            'domain': domain,
            'classification': classification,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'other_name': other_name,
            'username': username,
            'roles': roles,
            'fields': fields,
        }

    def save_photo(self, username):
        photo_file = self.photo_path / f'{username}.webp'
        photo_index = self.user_count % NUM_PHOTOS
        orig_file = PHOTOS_DIR / f"{photo_index:03d}.webp"
        ref_file = self.photo_path / orig_file.name
        if not ref_file.exists():
            shutil.copy(orig_file, ref_file)
        d = os.getcwd()
        os.chdir(self.photo_path)
        os.symlink(ref_file.name, photo_file.name)
        os.chdir(d)

    def add_user(self):
        info = self.make_random_info()
        institution = self.add_institution(info)
        address = self.add_address(info)

        # 25% chance of being a reviewer if you are faculty or professional or postdoc
        is_reviewer = random.randint(0, 100) < 25 and info['classification'] in ['faculty', 'professional', 'postdoc']
        if is_reviewer:
            pk = self.add_reviewer(self.user_count, info['fields'])

        self.new_users.append({
            'model': 'users.user',
            'pk': self.user_count,
            'fields': {
                'created': '2024-12-30 20:49:59.049236+00:00',
                'modified': '2024-12-30 20:49:59.049236+00:00',
                'password': os.environ.get('DJANGO_FAKE_PASSWORD', ''),
                'username': info['username'],
                'institution': institution['pk'],
                'address': address,
                'classification': info['classification'],
                'first_name': info['first_name'],
                'last_name': info['last_name'],
                'other_names': info['other_name'],
                'email': info['email'],
                'roles': info['roles'] + '<reviewer>' if is_reviewer else info['roles'],
                'photo': f"/photo/{info['username']}.webp",
                'research_field': info['fields'],
            }
        })

        # save photo
        self.save_photo(info['username'])

    def add_users(self, count):
        for n in range(count):
            self.add_user()
            if n % 500 == 0:
                print(f'Added {n} users ...')

    def save(self):
        with open(self.data_path, 'w', encoding='utf-8') as file:
            yaml.dump(list(self.new_institutions.values()), file, sort_keys=False)
            yaml.dump(self.new_addresses, file, sort_keys=False)
            yaml.dump(self.new_users, file, sort_keys=False)
            yaml.dump(self.new_reviewers, file, sort_keys=False)


class FakeFacility:
    def __init__(self, name):
        self.name = name
        self.new_facilities = []
        self.new_configs = []
        self.new_config_items = []
        self.facility_count = 1
        self.config_count = 1
        self.config_item_count = 1
        self.fake = Faker()
        self.acronyms = {}
        self.techniques = defaultdict(list)

        path = Path(self.name)
        self.data_path = path / 'kickstart' / '000-facilities.yml'
        self.data_path.parent.mkdir(parents=True, exist_ok=True)

    def add_config(self, facility, tech):
        info = {
            'model': 'proposals.facilityconfig',
            'pk': self.config_count,
            'fields': {
                'created': '2024-12-30 20:49:59.049236+00:00',
                'modified': '2024-12-30 20:49:59.049236+00:00',
                'start_date': '2025-01-01',
                'accept': True,
                'facility': facility,
                'cycle': 1,
            }
        }
        self.new_configs.append(info)
        for item in tech['techniques']:
            self.new_config_items.append({
                'model': 'proposals.configitem',
                'pk': self.config_item_count,
                'fields': {
                    'created': '2024-12-30 20:49:59.049236+00:00',
                    'modified': '2024-12-30 20:49:59.049236+00:00',
                    'config': self.config_count,
                    'technique': item,
                    'track': 1,
                }
            })
            self.techniques[facility].append(self.config_item_count)
            self.config_item_count += 1
        self.config_count += 1

    def add_facilities(self):
        for i, tech in enumerate(TECHNIQUES.values()):
            source = random.choice(
                ['Insertion Device', 'Bend Magnet', 'Wiggler', 'Elliptical Polarized Undulator', 'In Vacuum Undulator'])
            source_acronym = make_acronym(source)
            name_acronym = tech['acronym']
            name = tech['name']
            acronym = f'{name_acronym}-{source_acronym}'
            self.acronyms[self.facility_count] = acronym
            description = f"{name} Beamline -- " + self.fake.paragraph(nb_sentences=2)
            info = {
                'model': 'beamlines.facility',
                'pk': self.facility_count,
                'fields': {
                    'created': '2024-12-30 20:49:59.049236+00:00',
                    'modified': '2024-12-30 20:49:59.049236+00:00',
                    'name': f'{name} Beamline',
                    'port': f'{i:02d}-{source_acronym}',
                    'source': source,
                    'acronym': acronym,
                    'url': f'https://{acronym.lower()}.bespoke.com/',
                    'flux': "{:0.4e} ph/s".format(random.randint(800, 12000) * 1e8),
                    'resolution': "{:0.4e} dE/E".format(random.randint(1, 5) * 1e-4),
                    'range': f"{random.randint(10, 5000)}-{random.randint(6000, 80000)} eV",
                    'state': random.choice(STATES),
                    'shift_size': random.choice([4, 8, 8, 8, 8, 8, 8]),
                    'flex_schedule': random.choice([True, False]),
                    'details': {
                        'beamtime': {"user": 45, "staff": 10, "beamteam": 10, "purchased": 25, "maintenance": 10}},
                    'description': description
                }
            }
            self.add_config(self.facility_count, tech)
            self.facility_count += 1
            self.new_facilities.append(info)

    def save(self):
        with open(self.data_path, 'w', encoding='utf-8') as file:
            yaml.dump(self.new_facilities, file, sort_keys=False)
            yaml.dump(self.new_configs, file, sort_keys=False)
            yaml.dump(self.new_config_items, file, sort_keys=False)


class FakeProposal:
    def __init__(self, name, users, facilities, techniques):
        self.name = name
        self.users = users
        self.facilities = dict(facilities)
        self.techniques = techniques
        self.new_samples = []
        self.new_proposals = []
        self.new_submissions = []
        self.new_reviews = []
        self.review_count = 1
        self.proposal_count = 1
        self.sample_count = 1
        self.submission_count = 1
        self.fake = Faker()

        path = Path(self.name)
        self.data_path = path / 'kickstart' / '003-proposals.yml'
        self.sample_path = path / 'kickstart' / '002-samples.yml'
        self.data_path.parent.mkdir(parents=True, exist_ok=True)

    def add_samples(self, user):
        return [self.add_sample(user) for _ in range(random.randint(1, 5))]

    def add_sample(self, user):
        sample = random.choice(SAMPLES)
        pk = self.sample_count
        state = random.choice(SAMPLE_STATES)
        units = SAMPLE_UNITS[state]
        quantity = random.randint(1, 1000)
        self.new_samples.append({
            'model': 'samples.sample',
            'pk': pk,
            'fields': {
                'created': '2024-12-30 20:49:59.049236+00:00',
                'modified': '2024-12-30 20:49:59.049236+00:00',
                'name': sample['name'],
                'owner': user,
                'source': sample['source'],
                'state': state,
                'kind': 'chemical',
                'description': self.fake.paragraph(nb_sentences=3),
                'hazard_types': random.sample(HAZARD_TYPES, random.randint(0, 3)),
                'hazards': random.sample(HAZARDS, random.randint(0, 4)),
                'is_editable': True,
                'details': {}
            }
        })
        self.sample_count += 1
        return {'sample': f'{pk}', 'quantity': f"{quantity} {units}"}

    def add_submission(self, proposal, cycle, track, techniques, facility):
        track_acronym = TRACKS[track]
        info = {
            'model': 'proposals.submission',
            'pk': self.submission_count,
            'fields': {
                'created': '2025-01-30 20:49:59.049236+00:00',
                'modified': '2025-01-30 20:49:59.049236+00:00',
                'proposal': proposal,
                'code': f"{track_acronym}{proposal:07_}".replace('_', '-'),
                'cycle': cycle,
                'track': track,
                'state': 0,
                'techniques': techniques,
            }
        }

        self.new_submissions.append(info)
        self.submission_count += 1

    def add_proposal(self):
        users = random.sample(self.users, random.randint(2, 5))
        facility = random.choice(list(self.techniques.keys()))
        acronym = self.facilities[facility]
        techniques = random.sample(self.techniques[facility], random.randint(1, len(self.techniques[facility])))
        areas = random.sample(SUBJECTS, random.randint(1, 3))
        title = self.fake.sentence(nb_words=10)
        delegate = {
            'first_name': users[1]['fields']['first_name'],
            'last_name': users[1]['fields']['last_name'],
            'email': users[1]['fields']['email']
        }
        delegate_username = users[1]['fields']['username']
        if random.randint(0, 100) < 5:
            delegate = {'first_name': 'Admin', 'last_name': 'User', 'email': 'admin@bespoke.com'}
            delegate_username = 'admin'
            team = users[1:]
        else:
            team = users[2:]

        cycle = random.choice([1, 2, 3, 4])
        track = random.choice([1, 2, 3])  # GA, RA, PA

        info = {
            'model': 'proposals.proposal',
            'pk': self.proposal_count,
            'fields': {
                'created': '2025-01-30 20:49:59.049236+00:00',
                'modified': '2025-01-30 20:49:59.049236+00:00',
                'form_type': 2,
                'code': f"{self.proposal_count:07_}".replace('_', '-'),
                'is_complete': False,
                'leader_username': users[0]['fields']['username'],
                'title': title,
                'delegate_username': delegate_username,
                'team': ''.join([f'<{user["fields"]["email"]}>' for user in users]),
                'state': 0,
                'spokesperson': users[0]['pk'],
                'areas': areas,
                'details': {
                    'title': title,
                    'leader': {
                        'first_name': users[0]['fields']['first_name'],
                        'last_name': users[0]['fields']['last_name'],
                        'email': users[0]['fields']['email']
                    },
                    'delegate': delegate,
                    'funding': ['NSERC', 'CIHR', 'SSHRC'],
                    'abstract': self.fake.paragraph(nb_sentences=10),
                    'subject': {
                        'areas': areas,
                        'keywords': '; '.join([self.fake.word() for _ in range(5)])
                    },
                    'first_cycle': cycle,
                    'team_members': [
                        {'first_name': user['fields']['first_name'],
                         'last_name': user['fields']['last_name'],
                         'email': user['fields']['email']}
                        for user in team
                    ],
                    'sample_list': self.add_samples(users[0]['pk']),
                    'beamline_reqs': [
                        {
                            'facility': facility,
                            'shifts': random.randint(1, 8),
                            'techniques': techniques,
                            'tags': [],
                            'procedure': self.fake.paragraph(nb_sentences=10),
                            'justification': self.fake.paragraph(nb_sentences=10),
                        }
                    ],
                    'pool': 1,
                    'scientific_merit': (
                            self.fake.paragraph(nb_sentences=15)
                            + random.choice(EQUATIONS)
                            + self.fake.paragraph(nb_sentences=15)
                    ),
                    'societal_impact': self.fake.paragraph(nb_sentences=8),
                    'team_capability': self.fake.paragraph(nb_sentences=12),
                    'sample_hazards': random.sample(HAZARD_TYPES, random.randint(0, 3)),
                    'sample_types': random.sample(SAMPLE_TYPES, random.randint(1, 3)),
                    'sample_handling': self.fake.paragraph(nb_sentences=8),
                    'invoice_address': {
                        'city': self.fake.city(),
                        'code': self.fake.postalcode(),
                        'region': self.fake.state(),
                        'street': self.fake.address(),
                        'country': self.fake.country(),
                    }
                }
            }
        }
        if random.choice([True, False]):
            info['fields']['is_complete'] = True
            info['fields']['state'] = 1
            facility_info = {
                'pk': facility,
                'acronym': acronym
            }
            self.add_submission(self.proposal_count, cycle, track, techniques, facility_info)

        self.new_proposals.append(info)
        self.proposal_count += 1

    def add_proposals(self, count):
        for _ in range(count):
            self.add_proposal()
        print(f'Added {count} proposals ...')

    def save(self):
        with open(self.sample_path, 'w') as file:
            yaml.dump(self.new_samples, file, sort_keys=False)
        with open(self.data_path, 'w') as file:
            yaml.dump(self.new_proposals, file, sort_keys=False)
            yaml.dump(self.new_submissions, file, sort_keys=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Data Generator for USO')
    parser.add_argument('name', metavar='name', type=str, help='Dataset Name', default='data')
    parser.add_argument('-u', '--users', type=int, help='Number of users', required=True)
    parser.add_argument('-p', '--proposals', type=int, help='Number of proposals', required=True)
    args = parser.parse_args()

    if os.path.exists(args.name):
        shutil.rmtree(args.name)

    fac_gen = FakeFacility(name=args.name)
    fac_gen.add_facilities()
    fac_gen.save()

    # generate users
    user_gen = FakeUser(name=args.name, facilities=fac_gen.acronyms)
    user_gen.add_users(args.users)
    user_gen.save()

    # generate proposals
    prop_gen = FakeProposal(
        name=args.name, users=user_gen.new_users, facilities=fac_gen.acronyms,
        techniques=fac_gen.techniques
    )
    prop_gen.add_proposals(args.proposals)
    prop_gen.save()
    print('All Done.')
