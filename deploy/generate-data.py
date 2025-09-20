#!/usr/bin/env python3

import argparse
import itertools
import os
import zipfile
import tempfile
import random
import shutil
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from django.utils import timezone


import dateutil.parser as date_parser
import numpy
import pytz
import yaml
from django.utils.timezone import make_aware
from faker import Faker
from unidecode import unidecode

# This script is used to generate fake data for the Bespoke system. some external data is used to generate the data
# such as sample photos, universities, country names, and sample types. The data is saved in YAML format

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

AVATARS_FILE = DATA_DIR / 'avatars.zip'


avatar_dir = tempfile.TemporaryDirectory()
PHOTOS_DIR = Path(avatar_dir.name)
# Extract avatars from the zip file if it exists
if AVATARS_FILE.exists():
    with zipfile.ZipFile(AVATARS_FILE, 'r') as zip_ref:
        zip_ref.extractall(PHOTOS_DIR)
NUM_PHOTOS = len(list(PHOTOS_DIR.glob('*.webp')))

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

CORE_PERMISSIONS = {
    'LAB-ACCESS': 1,
    'CRYO-WORK': 1,
    'HF-WORK': 0.5,
    'ANIMAL-WORK': 0.5,
    'BIOLAB-ACCESS': 1,
    'RADIOACTIVE-WORK': 1,
    'PATHOGEN-WORK': 1,
    'FACILITY-ACCESS': 4,
}

THIS_YEAR = datetime.now().year
YEAR_WEIGHTS = numpy.random.uniform(0, 1, size=(THIS_YEAR - 2009))
YEAR_WEIGHTS /= YEAR_WEIGHTS.sum()  # Normalize weights to sum to 1
YEARS = list(range(2009, THIS_YEAR))


fake = Faker()


class RandomDate:
    def __init__(self, start, offset):
        self.start = date_parser.parse(start)
        self.offset = offset
        self.index = 0

    def step(self):
        self.index += random.choice([-2, 5, -1, 1, 1, -1, 3])
        self.index = self.index % self.offset
        return (self.start + timedelta(days=self.index)).strftime('%Y-%m-%d')

    def __call__(self):
        return self.step()


class RandomChooser:
    def __init__(self, choices):
        self.choices = choices
        self.offset = len(choices)
        self.index = 0

    def step(self):
        self.index += random.choice([-2, 5, -1, 1, 1, -1, 3, 1, -1])
        self.index = self.index % self.offset
        return self.choices[self.index]

    def __call__(self):
        return self.step()


class LikertRandomizer:
    def __init__(self):
        self.choices = [1, 2, 3, 4, 5]
        self.weights = {}
        self.scores = {
            5: 'Excellent',
            4: 'Good',
            3: 'Fair',
            2: 'Poor',
            1: 'Very Poor'
        }

    def __call__(self, name, section):
        key = f'{section}.{name}'
        if 'ware' in name.lower():
            self.weights[key] = [1, 1, 3, 5, 1]
        elif 'ing' in name.lower():
            self.weights[key] = [6, 6, 4, 1, 1]
        elif name.endswith('lity'):
            self.weights[key] = [1, 1, 3, 7, 5]
        elif name.endswith('ood'):
            self.weights[key] = [1, 6, 6, 1, 1]
        elif 'beam' in name.lower():
            self.weights[key] = [1, 2, 4, 5, 2]
        elif 'support' in name.lower():
            self.weights[key] = [1, 1, 5, 7, 7]
        else:
            weights = [1, 1, 2, 4, 5]
            weights[random.randint(0, 4)] += random.randint(1, 5)
            self.weights[key] = weights
        score = random.choices(self.choices, weights=self.weights[key])[0]
        return {'label': self.scores[score], 'value': score}


random_likert_choice = LikertRandomizer()


def random_schedule(start_date, end_date):
    """
    Generates a random list of continuous time intervals between two dates
    according to a specific set of rules.

    Rules:
    - Intervals must start and end at either 08:00 or 16:00.
    - Intervals are non-overlapping.
    - Generates between 5 and 10 intervals per week (Tue 08:00 to Mon 08:00).
    - Random 0-24 hour gaps can occur between intervals.
    - Minimum interval duration is 8 hours.

    Args:
        start_date: The start date of the overall period
        end_date: The end date of the overall period

    Returns:
        list: A list of tuples, where each tuple contains the start and end
              datetime objects for an interval.
    """
    try:
        start_date = datetime.combine(start_date, datetime.min.time())
        end_date = datetime.combine(end_date, datetime.min.time())
    except ValueError:
        print("Error: Please provide dates in 'YYYY-MM-DD' format.")
        return []

    intervals = []

    # --- Step 1: 08:00 on first day
    cursor = start_date.replace(hour=8, minute=0, second=0, microsecond=0)

    # --- Step 2: process the week
    week_start = cursor
    week_end = end_date

    num_intervals_for_week = random.randint(5, 10)
    week_cursor = week_start

    # --- Step 3: Inner loop to generate intervals within the current week ---
    for _ in range(num_intervals_for_week):
        if week_cursor >= week_end:
            break # Stop if we've run out of time in the work week

        interval_start = week_cursor

        # --- Step 4: Calculate a valid random duration for the interval ---
        # First, find the maximum number of valid steps (8h or 16h blocks)
        # that can fit between the current position and the end of the week.
        max_steps = 0
        temp_time = interval_start
        while True:
            step_hours = 8 if temp_time.hour == 8 else 16
            if temp_time + timedelta(hours=step_hours) <= week_end:
                temp_time += timedelta(hours=step_hours)
                max_steps += 1
            else:
                break

        if max_steps == 0:
            # Can't fit even a minimum 8-hour interval.
            break

        # Now, pick a random number of steps to create the interval's duration.
        num_steps = random.randint(1, max_steps)
        interval_end = interval_start
        for _ in range(num_steps):
            step_hours = 8 if interval_end.hour == 8 else 16
            interval_end += timedelta(hours=step_hours)

        intervals.append((interval_start, interval_end))

        # --- Step 5: Calculate the start time for the next interval ---
        # Add a random gap between 0 and 24 hours.
        gap_hours = random.uniform(0, 24)
        next_start_base = interval_end + timedelta(hours=gap_hours)

        # Snap the resulting time to the next valid 08:00 or 16:00 slot.
        if next_start_base.hour < 8 or \
           (next_start_base.hour == 8 and next_start_base.minute == 0):
            week_cursor = next_start_base.replace(hour=8, minute=0, second=0, microsecond=0)
        elif next_start_base.hour < 16 or \
             (next_start_base.hour == 16 and next_start_base.minute == 0):
            week_cursor = next_start_base.replace(hour=16, minute=0, second=0, microsecond=0)
        else:
            next_day = next_start_base + timedelta(days=1)
            week_cursor = next_day.replace(hour=8, minute=0, second=0, microsecond=0)

    return intervals


def random_year():
    """Generate a random year between start and end."""
    return random.choices(YEARS, weights=YEAR_WEIGHTS)[0]


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


class FakeFeedback:
    def __init__(self, name='data'):
        self.new_surveys = []
        self.new_categories = []
        self.category_ids = {}
        self.new_ratings = []
        self.fake = Faker()
        self.ratings_count = 0
        self.categories_count = 0
        self.feedback_count = 0
        path = Path(name)
        self.data_path = path / 'kickstart' / '006-feedback.yml'

    def save(self):
        with open(self.data_path, 'w', encoding='utf-8') as file:
            yaml.dump(self.new_surveys, file, sort_keys=False)
            yaml.dump(self.new_categories, file, sort_keys=False)
            yaml.dump(self.new_ratings, file, sort_keys=False)

    def add_category(self, name):
        key = name.replace('_', ' ').capitalize()

        if key in self.category_ids:
            return self.category_ids[key]

        self.categories_count += 1
        pk = self.categories_count
        self.category_ids[key] = pk
        category = {
            'model': 'surveys.category',
            'pk': pk,
            'fields': {
                'name': key
            }
        }
        self.new_categories.append(category)
        return category['pk']

    def add_ratings(self, feedback_id, category, ratings):
        category_id = self.add_category(category)
        for rating in ratings:
            self.ratings_count += 1
            pk = self.ratings_count
            rating_obj = {
                'model': 'surveys.rating',
                'pk': pk,
                'fields': {
                    'feedback_id': feedback_id,
                    'category_id': category_id,
                    'name': rating['name'],
                    'label': rating['label'],
                    'value': rating['value'],
                }
            }
            self.new_ratings.append(rating_obj)

    def add_survey(self, cycle, beamline, user, date_str='2008-12-30'):
        self.feedback_count += 1
        pk = self.feedback_count
        feedback = {
            'model': 'surveys.feedback',
            'pk': pk,
            'fields': {
                'created': f'{date_str} 00:33:08.214086+00:00',
                'modified': f'{date_str} 00:33:08.214133+00:00',
                'form_type': 12,
                'is_complete': True,
                'user': user,
                'beamline': beamline,
                'cycle': cycle,
                'details': {
                    'machine_comments': self.fake.paragraph(nb_sentences=2),
                    'beamline_comments': self.fake.paragraph(nb_sentences=1),
                    'administration_comments': self.fake.paragraph(nb_sentences=2),
                    'amenities_comments': self.fake.paragraph(nb_sentences=2),
                    'amenities_desires': self.fake.paragraph(nb_sentences=1),
                    'amenities_lodging_comments': self.fake.paragraph(nb_sentences=2),
                    'amenities_lodging': random.choice(['Guest House', 'Hotel', 'Bed & Breakfast', 'Friends or Family']),
                    'amenities_lodging_reason': random.choice([
                        'Location', 'Price', 'Price', 'Price', 'Convenience', 'Amenities', 'Recommendation'
                    ]),
                },
            }
        }
        self.new_surveys.append(feedback)
        self.add_ratings(
            self.feedback_count, 'machine', [
                {'name': name, **random_likert_choice(name, (beamline, cycle))}
                for name in ['Reliability', 'Availability', 'Communication', 'Beam Stability']
            ]
        )
        self.add_ratings(
            self.feedback_count, 'beamline',
            [
                {'name': name, **random_likert_choice(name, (beamline, cycle))}
                for name in [
                    'Personnel', 'Environment', 'End-station', 'Equipment Quality', 'Beam Quality', 'Software',
                    'Hardware', 'Data Transfer', 'Beam Availability'
                ]
            ]
        )
        self.add_ratings(
            self.feedback_count,
            'administration',
            [
                {'name': name, **random_likert_choice(name, (beamline, cycle))}
                for name in [
                    'Parking', 'Training', 'Sign-in / Safety', 'Check-In Procedure', 'Administrative Support',
                    'Registration / Proposals', 'User Information / Web Pages'
                ]
            ],
        )
        self.add_ratings(
            self.feedback_count,
            'amenities',
            [
                {'name': name, **random_likert_choice(name, (beamline, cycle))}
                for name in [
                    'Food', 'Wi-Fi / Internet', 'Coffee / Vending Machines', 'User Lounges',
                    'Lodging', 'Showers / Lockers', 'Office / Printing'
                ]
            ],
        )


class FakeUser:
    def __init__(self, name='data', facilities=None):
        self.fake = Faker()
        self.name = name
        # update admin fields
        self.new_users = []
        self.user_permissions = defaultdict(set)
        self.new_institutions = {
            'Bespoke Facility': {
                'model': 'users.institution',
                'pk': 1,
                'fields': {
                    'created': '2008-12-30 20:49:59.049236+00:00',
                    'modified': '2008-12-30 20:49:59.049236+00:00',
                    'name': 'Bespoke Facility',
                    'city': 'Nome',
                    'country': ['CAN'],
                    'region': ['CA-SK'],
                    'sector': 'academic',
                    'domains': ["@bespoke.com"],
                    'state': 'exempt',
                }
            }
        }
        self.date_chooser = RandomDate('2008-12-30', 365)
        self.date = '2008-12-30'
        self.new_reviewers = []
        self.new_addresses = []

        self.user_count = 1
        self.reviewer_count = 1
        self.institution_count = 1
        self.address_count = 1
        self.photo_offset = random.randint(1, 20) * 2
        self.user_names = defaultdict(int)
        self.user_emails = set()
        self.facility_acronyms = {} if not facilities else facilities

        path = Path(name)
        self.data_path = path / 'kickstart' / '001-users.yml'
        self.photo_path = path / 'media' / 'photo'

        if self.photo_path.exists():
            shutil.rmtree(self.photo_path)

        self.photo_path.mkdir(parents=True, exist_ok=True)
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.save_photo('admin')  # make sure admin account has a photo also

    def make_username(self, first_name, last_name, other_name=''):
        username = unidecode(f'{first_name}{first_char(last_name)}{first_char(other_name)}'.lower())
        self.user_names[username] += 1
        if self.user_names[username] > 1:
            return f'{username}{self.user_names[username]}'
        return username

    def make_email(self, first_name, last_name, domain):
        base_email = unidecode(f'{first_name}.{last_name}{domain}').replace(' ', '').lower()
        email = base_email
        count = 1
        while email in self.user_emails:
            count += 1
            email = f'{first_name}.{last_name}{count}{domain}'.replace(' ', '').lower()
        self.user_emails.add(email)
        return email

    def add_address(self, info):
        self.address_count += 1
        pk = self.address_count
        self.new_addresses.append({
            'model': 'users.address',
            'pk': pk,
            'fields': {
                'created': f'{self.date} 20:48:59.049236+00:00',
                'modified': f'{self.date} 20:49:59.049236+00:00',
                'address_1': info['department'],
                'address_2': f"{info['address']}",
                'city': info['city'],
                'region': [info['region']],
                'postal_code': info['zip'],
                'country': [info['country']],
                'phone': info['phone'],
            }
        })
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
                'created': f'{self.date} 20:49:59.049236+00:00',
                'modified': f'{self.date} 20:49:59.049236+00:00',
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
                'created': f'{self.date} 20:48:59.049236+00:00',
                'modified': f'{self.date} 20:49:59.049236+00:00',
                'name': info['institution'],
                'city': info['city'],
                'region': [info['region']],
                'country': [info['country']],
                'sector': 'academic',
                'domains': info['domain'],
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
            country = 'CAN'
            city = 'Saskatoon'
            region = 'CA-SK'
            address = '1 Synchrotron Way'
            department = 'Beamline Operations'
            zip_code = 'AP00-M0001'
            roles = ['staff']
            classification = 'professional'
            fac = random.choice(list(self.facility_acronyms.values()))
            if random.choice([True, False]):
                roles += [f'staff:{fac.lower()}']
                if random.choice([True, False]):
                    roles += [f'admin:{fac.lower()}', f'reviewer:{fac.lower()}']
                elif random.choice([True, False]):
                    roles += [f'reviewer:{fac.lower()}']
            elif random.choice([True, True, False]):
                roles += [random.choice(ROLES)]
            if kind == 'male':
                first_name = fake_first_name_male(country)
            else:
                first_name = fake_first_name_female(country)
            last_name = fake_last_name(country)
        else:
            inst_info = random.choice(UNIVERSITIES)
            institution = inst_info['name']
            domain = inst_info['domain'][0] if inst_info['domain'] else f"@example.edu"
            roles = ['user']
            country = inst_info['country']
            city = inst_info['city']
            region = inst_info['region']
            address = self.fake.street_address()
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
        email = self.make_email(first_name, last_name, domain)
        return {
            'country': country,
            'city': city,
            'region': region,
            'address': address,
            'zip': zip_code,
            'phone': phone,
            'department': department,
            'institution': institution,
            'domain': [domain],
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
        photo_index = (self.user_count + self.photo_offset) % NUM_PHOTOS
        orig_file = PHOTOS_DIR / f"{photo_index:03d}.webp"
        ref_file = self.photo_path / orig_file.name
        if not ref_file.exists():
            shutil.copy(orig_file, ref_file)
        d = os.getcwd()
        os.chdir(self.photo_path)
        os.symlink(ref_file.name, photo_file.name)
        os.chdir(d)

    def add_user(self, date_string='2008-12-30'):
        self.date = date_string
        info = self.make_random_info()
        institution = self.add_institution(info)
        address = self.add_address(info)

        # 15% chance of being a reviewer if you are faculty or professional or postdoc
        is_reviewer = random.randint(0, 100) < 15 and info['classification'] in ['faculty', 'professional', 'postdoc']
        if is_reviewer:
            self.add_reviewer(self.user_count, info['fields'])

        self.user_permissions[self.user_count].update(
            random.choices(
                list(CORE_PERMISSIONS.keys()),
                weights=list(CORE_PERMISSIONS.values()),
                k=random.randint(2, 5)
            )
        )
        self.new_users.append({
            'model': 'users.user',
            'pk': self.user_count,
            'fields': {
                'created': f'{self.date} 20:49:59.049236+00:00',
                'modified': f'{self.date} 21:49:59.049236+00:00',
                'password': os.environ.get('DJANGO_FAKE_PASSWORD', ''),
                'username': info['username'],
                'institution': institution['pk'],
                'address': address,
                'classification': info['classification'],
                'first_name': info['first_name'],
                'last_name': info['last_name'],
                'other_names': info['other_name'],
                'email': info['email'],
                'roles': info['roles'] + ['reviewer'] if is_reviewer else info['roles'],
                'photo': f"/photo/{info['username']}.webp",
                'research_field': info['fields'],
            }
        })
        # save photo
        self.save_photo(info['username'])

    def add_users(self, count, date_string='2008-12-30'):
        for n in range(count):
            self.add_user(date_string)
        print(f'Added {count} users ...')
        return self.new_users

    def save(self):
        for i in range(len(self.new_users)):
            pk = self.new_users[i]['pk']
            self.new_users[i]['fields']['permissions'] = list(self.user_permissions[pk])

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
        self.fake = Faker('la')
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
                'created': '2010-01-01 20:49:59.049236+00:00',
                'modified': '2010-01-01 20:49:59.049236+00:00',
                'start_date': '2010-01-01',
                'accept': True,
                'facility': facility,
                'cycle': 1,
            }
        }
        self.new_configs.append(info)
        for item in tech['techniques']:
            for track in [1, 2, 3]:
                self.new_config_items.append({
                    'model': 'proposals.configitem',
                    'pk': self.config_item_count,
                    'fields': {
                        'created': '2010-01-01 20:49:59.049236+00:00',
                        'modified': '2010-01-01 20:49:59.049236+00:00',
                        'config': self.config_count,
                        'technique': item,
                        'track': track,
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
                    'created': f'2010-01-01 20:49:59.049236+00:00',
                    'modified': f'2010-01-01 20:49:59.049236+00:00',
                    'name': f'{name} Beamline',
                    'port': f'{i:02d}-{source_acronym}',
                    'source': source,
                    'acronym': acronym,
                    'url': f'https://{acronym.lower()}.bespoke.com/',
                    'flux': "{:0.4e} ph/s".format(random.randint(800, 12000) * 1e8),
                    'resolution': "{:0.4e} dE/E".format(random.randint(1, 5) * 1e-4),
                    'range': f"{random.randint(10, 5000)}-{random.randint(6000, 80000)} eV",
                    'state': random.choice(STATES),
                    'shift_size': random.choices([4, 8], weights=[1, 10])[0],
                    'flex_schedule': random.choices([True, False], weights=[3, 10])[0],
                    'details': {
                        'pools': {"1": 45, "2": 10, "3": 10, "4": 25, "5": 10}
                    },
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
    def __init__(self, name, facilities, techniques, num_users=50, num_proposals=50):

        self.name = name
        self.user_gen = FakeUser(name=name, facilities=facilities)
        self.feedback_gen = FakeFeedback(name=name)
        self.users = []
        self.facilities = dict(facilities)
        self.permissions = {
            acronym: 1.0
            for acronym in self.facilities.values()
        }
        self.techniques = techniques
        self.new_samples = []
        self.new_cycles = []
        self.new_schedules = []
        self.new_proposals = []
        self.new_submissions = []
        self.new_projects = []
        self.new_events = []
        self.new_reviews = []
        self.new_beamtime = []
        self.cycle_beamtime = defaultdict(list)
        self.cycle_beamline_projects = {}
        self.review_count = 1
        self.proposal_count = 1
        self.sample_count = 1
        self.cycle_count = 1
        self.project_count = 1
        self.allocation_count = 1
        self.beamtime_count = 1
        self.material_count = 1
        self.project_samples_count = 1

        self.mode_count = 1
        self.submission_count = 1
        self.fake = Faker('la')
        self.year = 2014
        user_offset = num_users // 5
        self.user_count_chooser = RandomChooser(
            list(range(num_users - user_offset, num_users + user_offset))
        )
        prop_offset = num_proposals // 5
        self.proposal_count_chooser = RandomChooser(
            list(range(num_proposals - prop_offset, num_proposals + prop_offset))
        )
        self.score_chooser = RandomChooser([1, 1, 1, 3, 3, 3, 2, 2, 2, 2, 4])

        path = Path(self.name)
        self.data_path = path / 'kickstart' / '003-proposals.yml'
        self.sample_path = path / 'kickstart' / '002-samples.yml'
        self.events_path = path / 'kickstart' / '004-events.yml'
        self.reviews_path = path / 'kickstart' / '005-reviews.yml'
        self.project_path = path / 'kickstart' / '006-projects.yml'
        self.beamtime_path = path / 'kickstart' / '007-beamtime.yml'
        self.data_path.parent.mkdir(parents=True, exist_ok=True)

    def add_samples(self, user, date_str):
        return [self.add_sample(user, date_str) for _ in range(random.randint(1, 4))]

    def add_sample(self, user, date_str):
        sample = random.choice(SAMPLES)
        pk = self.sample_count
        state = random.choice(SAMPLE_STATES)
        units = SAMPLE_UNITS[state]
        quantity = random.randint(1, 1000)
        self.new_samples.append({
            'model': 'samples.sample',
            'pk': pk,
            'fields': {
                'created': f'{date_str} 20:49:59.049236+00:00',
                'modified': f'{date_str} 20:49:59.049236+00:00',
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

    def add_submission(self, info):
        proposal = info['proposal']
        date_str = info['date']
        cycle = info['cycle']
        track = info['track']
        facility_techniques = info['techniques']
        track_acronym = TRACKS[track]

        start_date = date_parser.parse(date_str)
        state = 1
        if start_date < datetime.now():
            state = 3
        submission = {
            'model': 'proposals.submission',
            'pk': self.submission_count,
            'fields': {
                'created': f'{date_str} 20:49:59.049236+00:00',
                'modified': f'{date_str} 20:49:59.049236+00:00',
                'proposal': proposal,
                'code': f"{track_acronym}{proposal:07_}".replace('_', '-'),
                'cycle': cycle,
                'track': track,
                'state': state,
                'techniques': list(itertools.chain(*facility_techniques.values())),
            }
        }

        info['submission'] = self.submission_count
        self.new_submissions.append(submission)
        tech_scores = self.add_technical_reviews(track_acronym, facility_techniques.keys(), date_str)
        good_tech_scores = []
        for fac, score in tech_scores.items():
            # remove failing facilities
            if score > 3:
                del info['techniques'][fac]
            else:
                good_tech_scores.append(score)
        sci_score = self.add_scientific_reviews(track_acronym, date_str)
        safe_score = 0
        if track == 2:
            safe_score = self.add_safety_review(track_acronym, date_str)

        avg_tech_score = sum(good_tech_scores) / len(good_tech_scores) if good_tech_scores else 4.0
        info['scores'] = {
            'technical': avg_tech_score,
            'scientific': sci_score,
            'safety': safe_score
        }
        info['score'] = sci_score

        # Add Project
        if avg_tech_score <= 3 and sci_score <= 4 and safe_score <= 4:
            submission['fields']['approved'] = True
            self.add_project(info)
        else:
            submission['fields']['approved'] = False

        self.submission_count += 1

    def add_technical_reviews(self, track, facilities, date_str):
        date_chooser = RandomDate(date_str, 3)
        cycle = self.new_cycles[-1]['pk']
        submission = self.new_submissions[-1]['pk']
        date_str = date_chooser()
        fac_scores = {}
        for fac in facilities:
            acronym = self.facilities[fac].lower()
            score = self.score_chooser()
            fac_scores[fac] = score
            self.new_reviews.append({
                'model': 'proposals.review',
                'pk': self.review_count,
                'fields': {
                    'created': f'{date_str} 20:49:59.049236+00:00',
                    'modified': f'{date_str} 20:49:59.049236+00:00',
                    'details': {
                        'facility': fac,
                        'comments': self.fake.sentence(nb_words=random.randint(5, 15)),
                        'risk_level': random.randint(1, 4),
                        'suitability': score,
                        'progress': {'total': 100, 'required': 100},
                    },
                    'form_type': 4,
                    'is_complete': True,
                    'content_type': ['proposals', 'submission'],
                    'object_id': submission,
                    'role': f'reviewer:{acronym}',
                    'state': 3,
                    'score': score,
                    'due_date': date_str,
                    'cycle': cycle,
                    'type': 2,
                    'stage': [track, 1]
                }
            })
            self.review_count += 1
        return fac_scores

    def add_scientific_reviews(self, track, date_str):
        cycle = self.new_cycles[-1]['pk']
        submission = self.new_submissions[-1]['pk']
        date_chooser = RandomDate(date_str, 15)
        all_scores = []
        for i in range(random.choice([2, 4])):
            scores = [self.score_chooser() for _ in range(3)]
            all_scores.extend(scores)
            date_str = date_chooser()
            self.new_reviews.append(
                {
                    'model': 'proposals.review',
                    'pk': self.review_count,
                    'fields': {
                        'created': f'{date_str} 20:49:59.049236+00:00',
                        'modified': f'{date_str} 20:49:59.049236+00:00',
                        'details': {
                            'comments': self.fake.sentence(nb_words=random.randint(5, 15)),
                            'risk_level': random.randint(1, 4),
                            'capability': scores[0],
                            'suitability': scores[1],
                            'scientific_merit': scores[2],
                            'progress': {'total': 95, 'required': 100},
                        },
                        'form_type': 3,
                        'is_complete': True,
                        'content_type': ['proposals', 'submission'],
                        'object_id': submission,
                        'role': 'reviewer',
                        'state': 3,
                        'score': sum(scores) / len(scores),
                        'due_date': date_str,
                        'cycle': cycle,
                        'type': 1,
                        'stage': [track, 2]
                    }
                }
            )
            self.review_count += 1
        return sum(all_scores) / len(all_scores) if all_scores else 0.0

    def add_safety_review(self, track, date_str):
        score = self.score_chooser()
        submission = self.new_submissions[-1]['pk']
        date_chooser = RandomDate(date_str, 15)
        date_str = date_chooser()
        cycle = self.new_cycles[-1]['pk']
        self.new_reviews.append(
            {
                'model': 'proposals.review',
                'pk': self.review_count,
                'fields': {
                    'created': f'{date_str} 20:49:59.049236+00:00',
                    'modified': f'{date_str} 20:49:59.049236+00:00',
                    'details': {
                        'comments': self.fake.sentence(nb_words=random.randint(5, 15)),
                        'risk_level': score,
                        'progress': {'total': 100, 'required': 100},
                    },
                    'form_type': 15,
                    'is_complete': True,
                    'content_type': ['proposals', 'submission'],
                    'object_id': submission,
                    'role': f'safety-reviewer',
                    'state': 3,
                    'score': score,
                    'due_date': date_str,
                    'cycle': cycle,
                    'type': 7,
                    'stage': [track, 3]
                }
            }
        )
        self.review_count += 1
        return score

    def add_material_review(self, material, cycle, date_str):
        self.new_reviews.append({
            'model': 'proposals.review',
            'pk': self.review_count,
            'fields': {
                'created': f'{date_str} 20:49:59.049236+00:00',
                'modified': f'{date_str} 20:49:59.049236+00:00',
                'details': {},
                'form_type': 5,
                'is_complete': False,
                'content_type': ['projects', 'material'],
                'object_id': material,
                'role': f'safety-approver',
                'state': 1,
                'score': 0.0,
                'cycle': cycle,
                'type': 6,
            }
        })
        self.review_count += 1

    def add_cycles(self):
        while self.year <= datetime.now().year + 1:
            self.add_cycle()

    def add_cycle(self):
        year = self.year
        if self.cycle_count % 2 == 1:
            start_date = f'{year}-01-01'
            end_date = f'{year}-12-31'
            open_date = f'{year-1}-08-07'
            close_date = f'{year-1}-09-07'
            due_date = f'{year-1}-10-16'
            alloc_date = f'{year-1}-10-30'
            name = f'{year} Jan-Jun'
            type_id = 1

        else:
            start_date = f'{year}-07-01'
            end_date = f'{year+1}-01-01'
            open_date = f'{year}-02-05'
            close_date = f'{year}-03-05'
            due_date = f'{year}-04-16'
            alloc_date = f'{year}-04-30'
            name = f'{year} Jul-Dec'
            type_id = 2
            self.year += 1

        self.new_schedules.append({
            'model': 'scheduler.schedule',
            'pk': self.cycle_count,
            'fields': {
                'created': f'{year-1}-11-01 20:49:59.049236+00:00',
                'modified': f'{year-1}-11-01 20:49:59.049236+00:00',
                'description': f'{name}: Schedule',
                'state': 'live',
                'config_id': 1,
                'start_date': start_date,
                'end_date': end_date,
            }
        })
        self.add_modes(self.cycle_count, start_date, end_date)
        info = {
            'model': 'proposals.reviewcycle',
            'pk': self.cycle_count,
            'fields': {
                'created': f'{year-1}-11-01 20:49:59.049236+00:00',
                'modified': f'{year-1}-11-01 20:49:59.049236+00:00',
                'start_date': start_date,
                'end_date': end_date,
                'type_id': type_id,
                'open_date': open_date,
                'close_date': close_date,
                'alloc_date': alloc_date,
                'due_date': due_date,
                'schedule_id': self.cycle_count,
            }
        }
        self.new_cycles.append(info)
        print('Added cycle ', self.cycle_count)
        cycle_info = {
            'cycle': self.cycle_count,
            'start_date': start_date,
            'end_date': end_date,
            'type_id': type_id,
            'open_date': open_date,
            'close_date': close_date,
            'alloc_date': alloc_date,
            'due_date': due_date,
        }
        self.users = self.user_gen.add_users(self.user_count_chooser() + self.cycle_count * 2, open_date)
        self.add_proposals(cycle_info)
        self.cycle_count += 1

    def add_modes(self, schedule_id, start_date, end_date):
        start = date_parser.parse(start_date).date()
        iso = start.isocalendar()
        d_start = start + timedelta(days=(1 - iso.weekday))  # First Monday
        end = date_parser.parse(end_date).date()
        num_weeks = 0
        shutdown_after = random.randint(12, 14)
        shutdown_period = random.randint(3, 5)
        while d_start < end:
            if start > d_start:
                shift_start = start
            else:
                shift_start = d_start
            iso = shift_start.isocalendar()
            if iso.weekday == 1:
                shift_end = shift_start + timedelta(days=1)
                mode = random.choice([3, 3, 3, 4, 4, 5, 2])
            else:
                shift_end = shift_start + timedelta(days=(7 - iso.weekday + 1))   # Next Monday
                num_weeks += 1
                mode = 1
            shift_end = min(shift_end, end)

            # shutdown period after 16 weeks
            if shutdown_after < num_weeks <= shutdown_after + shutdown_period:
                mode = 5

            if shift_start.month == 12 and shift_start.day > 20:
                mode = 5
            self.new_events.append({
                'model': 'scheduler.mode',
                'pk': self.mode_count,
                'fields': {
                    'created': f'{start_date} 20:49:59.049236+00:00',
                    'modified': f'{start_date} 20:49:59.049236+00:00',
                    'start': f"{shift_start.strftime('%Y-%m-%d')} 14:00:00+00:00",
                    'end': f"{shift_end.strftime('%Y-%m-%d')} 14:00:00+00:00",
                    'schedule': schedule_id,
                    'comments': '',
                    'kind': mode,
                    'tags': [],
                }
            })
            self.mode_count += 1
            d_start = shift_end

            if mode == 1:
                self.cycle_beamtime[schedule_id].append((shift_start, shift_end))

    def get_random_facility_req(self):
        facility = random.choice(list(self.techniques.keys()))
        techniques = random.sample(self.techniques[facility], random.randint(1, len(self.techniques[facility])))
        return {
            'facility': facility,
            'shifts': random.randint(1, 8),
            'techniques': techniques,
            'tags': [],
            'procedure': self.fake.paragraph(nb_sentences=4),
            'justification': self.fake.paragraph(nb_sentences=4),
        }

    def add_proposal(self, cycle_info):
        cycle = cycle_info['cycle']
        date_str = cycle_info['date']
        end_date = date_parser.parse(date_str).date() + timedelta(days=30)
        users = random.sample(self.users, random.randint(2, 5))
        areas = random.sample(SUBJECTS, random.randint(1, 3))
        facility_reqs = []
        techniques = []
        facility_techniques = {}
        num_reqs = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.05], k=1)[0]
        for _ in range(num_reqs):
            req = self.get_random_facility_req()
            while req['facility'] in facility_techniques:
                req = self.get_random_facility_req()
            facility_techniques[req['facility']] = req['techniques']
            techniques.extend(req['techniques'])
            facility_reqs.append(req)

        title = self.fake.sentence(nb_words=10)
        delegate = {
            'first_name': users[1]['fields']['first_name'],
            'last_name': users[1]['fields']['last_name'],
            'email': users[1]['fields']['email']
        }
        delegate_username = users[1]['fields']['username']
        if random.randint(0, 100) < 2:
            delegate = {'first_name': 'Admin', 'last_name': 'User', 'email': 'admin@bespoke.com'}
            delegate_username = 'admin'

        track = random.choices([1, 2, 3], weights=[8, 2, 3])[0]  # GA, RA, PA
        submission_team = [
            user['fields']['email'] for user in users
        ]
        leader_username = users[0]['fields']['username']
        submission_info = {
            'proposal': self.proposal_count,
            'title': title,
            'team_members': [
                {'first_name': user['fields']['first_name'],
                 'last_name': user['fields']['last_name'],
                 'email': user['fields']['email']}
                for user in users
            ],
            'users': [user['pk'] for user in users],
            'spokesperson': users[0]['pk'],
            'leader': leader_username,
            'delegate': delegate_username,
            'techniques': facility_techniques,
            'cycle': cycle,
            'track': track,
            'date': date_str,
            'samples': self.add_samples(users[0]['pk'], date_str),
            'invoice_address': {
                'city': self.fake.city(),
                'code': self.fake.postalcode(),
                'region': self.fake.state(),
                'street': self.fake.address(),
                'country': self.fake.country(),
            }
        }
        info = {
            'model': 'proposals.proposal',
            'pk': self.proposal_count,
            'fields': {
                'created': f'{date_str} 20:49:59.049236+00:00',
                'modified': f'{date_str} 20:49:59.049236+00:00',
                'form_type': 2,
                'code': f"{self.proposal_count:07_}".replace('_', '-'),
                'is_complete': False,
                'leader_username': leader_username,
                'title': title,
                'delegate_username': delegate_username,
                'team': submission_team,
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
                    'abstract': self.fake.paragraph(nb_sentences=3),
                    'subject': {
                        'areas': areas,
                        'keywords': '; '.join([self.fake.word() for _ in range(random.randint(1, 3))]),
                    },
                    'first_cycle': cycle,
                    'team_members': submission_info['team_members'],
                    'sample_list': submission_info['samples'],
                    'beamline_reqs': facility_reqs,
                    'pool': 1,
                    'scientific_merit': (
                            self.fake.paragraph(nb_sentences=4)
                            + random.choice(EQUATIONS)
                            + self.fake.paragraph(nb_sentences=5)
                    ),
                    'societal_impact': self.fake.paragraph(nb_sentences=3),
                    'team_capability': self.fake.paragraph(nb_sentences=3),
                    'sample_hazards': random.sample(HAZARD_TYPES, random.randint(0, 3)),
                    'sample_types': random.sample(SAMPLE_TYPES, random.randint(1, 3)),
                    'sample_handling': self.fake.paragraph(nb_sentences=2),
                    'invoice_address': submission_info['invoice_address'],
                }
            }
        }
        facility_permissions = [
            f'{self.facilities[fac]}-USER' for fac in facility_techniques.keys()
        ]
        for user in submission_info['users']:
            user_perms = random.choices(facility_permissions, k=random.randint(1, len(facility_permissions)))
            if random.randint(1, 10) < 7:
                self.user_gen.user_permissions[user].update(user_perms)

        facilities = list(facility_techniques.keys())
        if end_date < datetime.now().date():
            info['fields']['is_complete'] = True
            info['fields']['state'] = 1
            submission_info['cycle_info'] = cycle_info
            self.add_submission(submission_info)

            if random.randint(0, 100) < 50 and facilities:
                # Add feedback for some proposals
                feedback_date = date_parser.parse(date_str).date() + timedelta(days=random.randint(2, 180))
                user = random.randint(1, self.user_gen.user_count)
                beamline = random.choice(facilities)
                self.feedback_gen.add_survey(cycle, beamline, user, feedback_date.strftime('%Y-%m-%d'))
        self.new_proposals.append(info)
        self.proposal_count += 1

    def add_project(self, info):
        cycle_info = info['cycle_info']
        pool = random.choices([1, 2, 3, 4, 5], weights=[75, 10, 20, 10, 5])[0]
        pool_code = {
            1: 'G',
            2: 'S',
            3: 'P',
            4: 'B',
            5: 'E'
        }[pool]
        code = f"{info['cycle']:03d}{pool_code}-{self.project_count:05d}"
        end_date = date_parser.parse(cycle_info['start_date']).date()
        end_date = end_date.replace(year=end_date.year + 2)
        cycle = cycle_info['cycle']
        self.new_projects.append({
            'model': 'projects.project',
            'pk': self.project_count,
            'fields': {
                'created': f'{info["date"]} 20:49:59.049236+00:00',
                'modified': f'{info["date"]} 20:49:59.049236+00:00',
                'start_date': cycle_info['start_date'],
                'end_date': end_date.strftime('%Y-%m-%d'),
                'proposal': info['proposal'],
                'code': code,
                'pool': pool,
                'cycle': cycle,
                'spokesperson': info['spokesperson'],
                'title': info['title'],
                'leader': [info['leader']],
                'delegate': [info['delegate']],
                'details': {
                    'team_members': info['team_members'],
                    'invoice_address': info['invoice_address'],
                },
                'submissions': [info['submission']],
                'team': info['users'],
                'techniques': list(itertools.chain(*info['techniques'].values())),
                'tags': [],
            }
        })

        # Add Materials
        approval = random.choices(['approved', 'pending', 'denied'], weights=[0.6, 0.3, 0.05])[0]
        self.new_projects.append({
            'model': 'projects.material',
            'pk': self.material_count,
            'fields': {
                'created': f'{info["date"]} 20:49:59.049236+00:00',
                'modified': f'{info["date"]} 20:49:59.049236+00:00',
                'project': self.project_count,
                'code': f'{code}M001',
                'procedure': self.fake.paragraph(nb_sentences=2),
                'waste': [],
                'disposal': '',
                'state': approval,
                'equipment': [],
                'permissions': {},
                'risk_level': random.randint(1, 4),
                'controls': [],
            }
        })

        self.add_material_review(self.material_count, cycle, info['date'])

        # Add Project samples
        for sample in info['samples']:
            sample_approval = 'approved' if approval == 'approved' else 'pending'
            self.new_projects.append({
                'model': 'projects.projectsample',
                'pk': self.project_samples_count,
                'fields': {
                    'created': f'{info["date"]} 20:49:59.049236+00:00',
                    'modified': f'{info["date"]} 20:49:59.049236+00:00',
                    'state': sample_approval,
                    'material': self.material_count,
                    'sample': int(sample['sample']),
                    'quantity': sample['quantity'],
                }
            })
            self.project_samples_count += 1

        if cycle not in self.cycle_beamline_projects:
            self.cycle_beamline_projects[cycle] = defaultdict(list)

        for fac in info['techniques'].keys():
            requested = random.randint(1, 8)
            self.cycle_beamline_projects[cycle][fac].append(self.project_count)
            self.new_projects.append({
                'model': 'projects.allocation',
                'pk': self.allocation_count,
                'fields': {
                    'created': f'{info["date"]} 20:49:59.049236+00:00',
                    'modified': f'{info["date"]} 20:49:59.049236+00:00',
                    'project': self.project_count,
                    'beamline': fac,
                    'cycle': cycle_info['cycle'],
                    'procedure': self.fake.paragraph(nb_sentences=2),
                    'justification': self.fake.paragraph(nb_sentences=2),
                    'shift_request': requested,
                    'shifts': random.randint(1, requested),
                    'score': info['score'],
                    'scores': info['scores'],
                    'declined': False,
                    'discretionary': False,
                }
            })
            self.allocation_count += 1

        self.project_count += 1
        self.material_count += 1

    def add_proposals(self, cycle_info):
        cycle = cycle_info['cycle']
        open_date = cycle_info['open_date']
        count = self.proposal_count_chooser() + 2 * cycle
        date_chooser = RandomDate(open_date, 30)
        for _ in range(count):
            cycle_info['date'] = date_chooser()
            self.add_proposal(cycle_info)
        print(f'Added {count} proposals for cycle {cycle}...')

    def add_beamtimes(self):
        for cycle, beamline_projects in self.cycle_beamline_projects.items():
            date_str = f'{self.year + cycle // 2}-01-01'
            for beamline, projects in beamline_projects.items():
                available_periods = list(itertools.chain(*[
                    random_schedule(*week) for week in self.cycle_beamtime[cycle]
                ]))
                random.shuffle(available_periods)
                index = 0
                while len(available_periods) > 0:
                    project = projects[index % len(projects)]
                    index += 1
                    period = available_periods.pop()
                    start_time, end_time = period

                    self.new_beamtime.append({
                        "model": "projects.beamtime",
                        "pk": self.beamtime_count,
                        "fields": {
                            "created": f"{date_str}T03:30:57.246Z",
                            "modified": f"{date_str}T03:30:57.246Z",
                            "start": start_time.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
                            "end": end_time.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
                            "cancelled": False,
                            "schedule": cycle,
                            "comments": "",
                            "project": project,
                            "beamline": beamline,
                            "tags": []
                        }
                    })
                    self.beamtime_count += 1

    def save(self):
        self.add_beamtimes()
        self.user_gen.save()
        with open(self.sample_path, 'w') as fobj:
            yaml.dump(self.new_samples, fobj, sort_keys=False)
        with open(self.data_path, 'w') as fobj:
            yaml.dump(self.new_schedules, fobj, sort_keys=False)
            yaml.dump(self.new_cycles, fobj, sort_keys=False)
            yaml.dump(self.new_proposals, fobj, sort_keys=False)
            yaml.dump(self.new_submissions, fobj, sort_keys=False)
        with open(self.events_path, 'w') as fobj:
            yaml.dump(self.new_events, fobj, sort_keys=False)
        with open(self.reviews_path, 'w') as fobj:
            yaml.dump(self.new_reviews, fobj, sort_keys=False)
        self.feedback_gen.save()
        with open(self.project_path, 'w') as fobj:
            yaml.dump(self.new_projects, fobj, sort_keys=False)

        with open(self.beamtime_path, 'w') as fobj:
            yaml.dump(self.new_beamtime, fobj, sort_keys=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Data Generator for USO')
    parser.add_argument('name', metavar='name', type=str, help='Directory to save data')
    parser.add_argument('-u', '--users', type=int, help='Starting number of users per cycle', default=100)
    parser.add_argument('-p', '--proposals', type=int, help='Starting number of proposals per cycle', default=75)
    args = parser.parse_args()

    fac_gen = FakeFacility(name=args.name)
    fac_gen.add_facilities()
    fac_gen.save()

    # generate proposals
    prop_gen = FakeProposal(
        name=args.name, facilities=fac_gen.acronyms,
        techniques=fac_gen.techniques,  num_users=args.users, num_proposals=args.proposals,
    )
    prop_gen.add_cycles()
    prop_gen.save()
    print('All Done.')
