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


class RandomWalk:

    def __init__(self, min_value=0, max_value=10):
        self.min_value = min_value
        self.max_value = max_value
        self.values = list(range(min_value, max_value + 1))
        self.current = random.choice(range(len(self.values)))

    def step(self):
        self.current += random.choice([-1, 1, 1, 1])
        self.current = self.current % len(self.values)
        return self.values[self.current]

    def __call__(self, name, section):
        return self.step()


class BiasedRandom:
    def __init__(self):
        self.choices = [1, 2, 3, 4, 5]
        self.weights = {}

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
        return random.choices(self.choices, weights=self.weights[key])[0]


#randomizer = RandomWalk(10, 50)
randomizer = BiasedRandom()


def random_likert_choice(name, section):
    scores = {
        5: 'Excellent',
        4: 'Good',
        3: 'Fair',
        2: 'Poor',
        1: 'Very Poor'
    }
    score = randomizer(name, section)
    return {'label': scores[score], 'value': score}


class FakeSurvey:

    def __init__(self):
        self.new_surveys = []
        self.new_categories = []
        self.category_ids = {}
        self.new_ratings = []
        self.fake = Faker()
        self.data_path = 'surveys.yml'
        self.ratings_count = 0
        self.categories_count = 0
        self.feedback_count = 0

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

    def add_survey(self):
        self.feedback_count += 1
        pk = self.feedback_count
        cycle_id = random.randint(1, 5)
        beamline_id = random.randint(1, 13)
        feedback = {
            'model': 'surveys.feedback',
            'pk': pk,
            'fields': {
                'created': '2025-09-07 00:33:08.214086+00:00',
                'modified': '2025-09-07 00:33:08.214133+00:00',
                'form_type': 12,
                'is_complete': True,
                'user_id': random.choice([random.randint(1, 118), random.randint(121, 820)]),
                'beamline_id': beamline_id,
                'cycle_id': cycle_id,
                'details': {
                    'progress': {
                        'total': 95.0,
                        'required': 100.0
                    },
                    'active_page': random.randint(1, 3),
                    'form_action': random.choice(['submit', 'save']),
                    'machine_comments': self.fake.paragraph(nb_sentences=2),
                    'beamline_comments': self.fake.paragraph(nb_sentences=3),
                    'administration_comments': self.fake.paragraph(nb_sentences=2),
                    'amenities_comments': self.fake.paragraph(nb_sentences=2),
                    'amenities_desires': self.fake.paragraph(nb_sentences=1),
                    'amenities_lodging_comments': self.fake.paragraph(nb_sentences=3),
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
                {'name': name, **random_likert_choice(name, (beamline_id, cycle_id))}
                for name in ['Reliability', 'Availability', 'Communication', 'Beam Stability']
            ]
        )
        self.add_ratings(
            self.feedback_count, 'beamline',
            [
                {'name': name, **random_likert_choice(name, (beamline_id, cycle_id))}
                for name in [
                    'Personnel', 'Environment', 'End-station', 'Equipment Quality', 'Beam Quality', 'Software',
                    'Hardware', 'Data Transfer', 'Availability'
                ]
            ]
        )
        self.add_ratings(
            self.feedback_count,
            'administration',
            [
                {'name': name, **random_likert_choice(name, (beamline_id, cycle_id))}
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
                {'name': name, **random_likert_choice(name, (beamline_id, cycle_id))}
                for name in [
                    'Food', 'Wi-Fi / Internet', 'Coffee / Vending Machines', 'User Lounges',
                    'Lodging', 'Showers / Lockers', 'Office / Printing'
                ]
            ],
        )


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

