import random

import faker
from django.utils import timezone

DEFAULT = {
    'scientific': {
        'comments': 'Good proposal',
        'progress': {'total': 80.0, 'required': 100.0},
        'capability': 3,
        'active_page': 1,
        'form_action': 'submit',
        'suitability': 3,
        'scientific_merit': 2
    },
    'technical': {
        'comments': 'Lorem porttitor aenean elit sit .',
        'facility': 2,
        'progress': {'total': 60.0, 'required': 100.0},
        'risk_level': 2,
        'active_page': 1,
        'form_action': 'submit',
        'suitability': 2
    }
}


def generate_fake_review(size=100, kind='scientific'):
    from proposals.models import Review

    fake = faker.Faker()
    for r in Review.objects.filter(type__code=kind, is_complete=False).order_by('?')[:size]:
        existing = r.details or {}
        details = {**DEFAULT[kind]}
        score = 0
        if kind == 'scientific':
            scores = random.randint(1, 4), random.randint(1, 4), random.randint(1, 4)
            details.update(
                capability=scores[0],
                suitability=scores[1],
                scientific_merit=scores[2],
                comments=fake.sentence(nb_words=random.randint(10, 30))
            )
            score = sum(scores) / 3
        elif kind == 'technical':
            scores = random.choice([1, 1, 1, 3, 3, 3, 3, 2, 2, 2, 2, 4]), random.randint(1, 4)
            details.update(
                risk_level=scores[0],
                suitability=scores[1],
                comments=fake.sentence(nb_words=random.randint(10, 30))
            )
            score = scores[1]
            details.update(existing)  # copy over facility
        Review.objects.filter(pk=r.pk).update(
            details=details,
            score=score,
            is_complete=True,
            state=Review.STATES.submitted,
            modified=timezone.now()
        )
