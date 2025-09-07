#!/usr/bin/env python3

import argparse
import os
import zipfile
import tempfile
import random
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy
import yaml
from faker import Faker
from unidecode import unidecode


class FakeSurvey:

    def __init__(self):
        self.new_surveys = []
        self.fake = Faker()
        self.data_path = 'surveys.yml'

    def save(self):
        with open(self.data_path, 'w', encoding='utf-8') as file:
            yaml.dump(self.new_surveys, file, sort_keys=False)

    def add_survey(self):
        pk = len(self.new_surveys) + 1
        likert_choices = ['Excellent', 'Good', 'Good', 'Fair', 'Poor', 'Very Poor', 'Excellent']
        info = {
            'model': 'surveys.feedback',
            'pk': pk,
            'fields': {
                'created': '2025-09-07 00:33:08.214086+00:00',
                'modified': '2025-09-07 00:33:08.214133+00:00',
                'form_type': 12,
                'is_complete': True,
                'user_id': random.choice([random.randint(1, 118), random.randint(121, 820)]),
                'beamline_id': random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]),
                'cycle_id': random.choice([1, 2, 3, 4, 5]),
                'details': {
                    'progress': {
                        'total': 95.0,
                        'required': 100.0
                    },
                    'active_page': random.randint(1, 3),
                    'form_action': random.choice(['submit', 'save']),
                    'machine': {
                        'Reliability': random.choice(likert_choices),
                        'Availability': random.choice(likert_choices),
                        'Communication': random.choice(likert_choices),
                        'Beam Stability': random.choice(likert_choices),
                    },
                    'beamline': {
                        'Personnel': random.choice(likert_choices),
                        'Environment': random.choice(likert_choices),
                        'End-station': random.choice(likert_choices),
                        'Equipment Quality': random.choice(likert_choices),
                        'Beam Quality': random.choice(likert_choices),
                        'Software': random.choice(likert_choices),
                        'Hardware': random.choice(likert_choices),
                        'Data Transfer': random.choice(likert_choices),
                        'Availability': random.choice(likert_choices),
                    },
                    'beamline_comments': self.fake.paragraph(nb_sentences=3),
                    'administration_comments': self.fake.paragraph(nb_sentences=2),
                    'administration': {
                        'Parking': random.choice(likert_choices),
                        'Training': random.choice(likert_choices),
                        'Sign-in / Safety': random.choice(likert_choices),
                        'Check-In Procedure': random.choice(likert_choices),
                        'Administrative Support': random.choice(likert_choices),
                        'Registration / Proposals': random.choice(likert_choices),
                        'User Information / Web Pages': random.choice(likert_choices),
                    },
                    'amenities_comments': self.fake.paragraph(nb_sentences=2),
                    'amenities_desires': self.fake.paragraph(nb_sentences=1),
                    'amenities_lodging_comments': self.fake.paragraph(nb_sentences=3),
                    'amenities_lodging_reason_comments': self.fake.paragraph(nb_sentences=2),
                    'amenities_lodging': random.choice(['Guest House', 'Hotel', 'Bed & Breakfast', 'Friends or Family']),
                    'amenities_overall': random.choice(likert_choices),
                    'amenities_lodging_reason': random.choice([
                        'Location', 'Price', 'Price', 'Price', 'Convenience', 'Amenities', 'Recommendation'
                    ]),
                },
            }
        }
        self.new_surveys.append(info)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Data Generator for USO')
    parser.add_argument('-n', '--number', type=int, help='Number of items', default=500)
    args = parser.parse_args()

    gen = FakeSurvey()
    for _i in range(args.number):
        gen.add_survey()
    gen.save()
    print(f'Generated {args.number} fake surveys in surveys.yml')
    print('All Done.')

