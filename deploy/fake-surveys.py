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
        self.current += random.choice([-1, 1])
        self.current = self.current % len(self.values)
        return self.values[self.current]

    def __call__(self):
        return self.step()


randomizer = RandomWalk(1, 5)


def random_likert_choice():
    scores = {
        5: 'Excellent',
        4: 'Good',
        3: 'Fair',
        2: 'Poor',
        1: 'Very Poor'
    }
    score = randomizer.step()
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

        feedback = {
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
                {'name': 'Reliability', **random_likert_choice()},
                {'name': 'Availability', **random_likert_choice()},
                {'name': 'Communication', **random_likert_choice()},
                {'name': 'Beam Stability', **random_likert_choice()},
            ]
        )
        self.add_ratings(
            self.feedback_count, 'beamline',
            [
                {'name': 'Personnel', **random_likert_choice()},
                {'name': 'Environment', **random_likert_choice()},
                {'name': 'End-station', **random_likert_choice()},
                {'name': 'Equipment Quality', **random_likert_choice()},
                {'name': 'Beam Quality', **random_likert_choice()},
                {'name': 'Software', **random_likert_choice()},
                {'name': 'Hardware', **random_likert_choice()},
                {'name': 'Data Transfer', **random_likert_choice()},
                {'name': 'Availability', **random_likert_choice()},
            ]
        )
        self.add_ratings(
            self.feedback_count,
            'administration',
            [
                {'name': 'Parking', **random_likert_choice()},
                {'name': 'Training', **random_likert_choice()},
                {'name': 'Sign-in / Safety', **random_likert_choice()},
                {'name': 'Check-In Procedure', **random_likert_choice()},
                {'name': 'Administrative Support', **random_likert_choice()},
                {'name': 'Registration / Proposals', **random_likert_choice()},
                {'name': 'User Information / Web Pages', **random_likert_choice()},
            ],
        )

        self.add_ratings(
            self.feedback_count,
            'amenities',
            [
                {'name': 'Food', **random_likert_choice()},
                {'name': 'Wi-Fi / Internet', **random_likert_choice()},
                {'name': 'Coffee / Vending Machines', **random_likert_choice()},
                {'name': 'User Lounges', **random_likert_choice()},
                {'name': 'Lodging', **random_likert_choice()},
                {'name': 'Showers / Lockers', **random_likert_choice()},
                {'name': 'Office / Printing', **random_likert_choice()},
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

