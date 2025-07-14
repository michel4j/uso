from typing import Any

from django.conf import settings
from django.db.models import F, Q, Avg

from beamlines.models import Facility
from misc.utils import debug_value
from proposals.models import ReviewType
from . import models

USO_SCORE_VETO_FUNCTION = getattr(settings, "USO_SCORE_VETO_FUNCTION", lambda score: score > 4)
USO_SAFETY_REVIEWS = getattr(settings, "USO_SAFETY_REVIEWS", [])
USO_SAFETY_APPROVAL = getattr(settings, "USO_SAFETY_APPROVAL", "approval")


def to_int(val, default=0):
    try:
        return int(val)
    except ValueError:
        return default


def calculate_end_date(start_date, duration):
    year = start_date.year
    year_offset, month_offset = divmod(start_date.month - 1 + duration * 6, 12)
    end_year = year + year_offset
    end_month = 1 + month_offset
    return start_date.replace(year=end_year, month=end_month)


def compress_scores(scores: dict, key: Any) -> dict:
    """
    Takes an optionally nested dictionary in which some values are dictionaries
    keyed with the provided key and replace the nested dictionary with the value of the key
    :param scores: nested dictionary
    :param key: key to extract
    :return: dictionary
    """
    first_pass = {
        k: (v.get(key, 'INVALID') if isinstance(v, dict) else v)
        for k, v in scores.items()
    }
    return {k: v for k, v in first_pass.items() if v != 'INVALID'}


def create_project(submission):
    proposal = submission.proposal
    cycle = submission.cycle
    track = submission.track

    if not submission.approved:
        # If the submission is not approved, do not create a project
        return

    expiry = calculate_end_date(cycle.end_date, track.duration - 1)
    info = {
        'proposal': proposal,
        'pool': submission.pool,
        'spokesperson': proposal.spokesperson,
        'title': proposal.title,
        'cycle': cycle,
        'start_date': cycle.start_date,
        'end_date': expiry,
        'details': {
            'delegate': proposal.details.get('delegate', {}),
            'leader': proposal.details.get('leader', {}),
            'team_members': proposal.details['team_members'],
            'invoice_address': proposal.details.get('invoice_address', {})
        }
    }

    requests = []
    facilities = submission.facilities().values_list('pk', flat=True)
    for req in proposal.details.get('beamline_reqs', []):
        facility_id = req.get('facility', 0)
        if facility_id not in facilities:
            continue
        requests.append({
            **req,
            'techniques': list(
                submission.techniques.filter(config__facility=facility_id).values_list('technique__pk', flat=True)
            )
        })

    passing_facilities = submission.get_facility_scores(passing_only=True)
    requests = submission.get_requests()

    if passing_facilities:
        passing_requests = {
            facility: details
            for facility, details in requests.items()
            if facility in passing_facilities
        }
        project, created = models.Project.objects.get_or_create(proposal=proposal, defaults=info)
        for facility, details in passing_requests.items():
            details['facility'] = details.get('facility', 0)
            project.techniques.add(*details['techniques'].all())
            create_project_allocations(project, details, cycle, scores=passing_facilities[facility])

        project.submissions.add(submission)
        project.refresh_team()

        # create materials
        material, created = models.Material.objects.get_or_create(
            project=project, defaults={
                'procedure': proposal.details.get('sample_handling', ''),
                'waste': proposal.details.get('waste_generation', []),
                'disposal': proposal.details.get('disposal_procedure', ''),
                'equipment': proposal.details.get('equipment', []),
            }
        )
        for sample in proposal.details.get('sample_list', []):
            p_sample, created = models.ProjectSample.objects.get_or_create(
                material=material, sample_id=sample['sample'],
                defaults={'quantity': sample.get('quantity', '')}
            )

        # Create MaterialReviews
        approval_type = ReviewType.objects.get(code=USO_SAFETY_APPROVAL)
        if approval_type:
            approval, created = material.reviews.get_or_create(
                type=approval_type, form_type=approval_type.form_type, defaults={
                    'cycle': cycle, 'state': models.Review.STATES.open, 'role': approval_type.role
                }
            )


def create_project_allocations(project, spec, cycle, shifts=0, shift_request=None, scores=None):
    if shift_request is None:
        shift_request = spec.get('shifts', 0)
    facilities = Facility.objects.filter(
        Q(kind=Facility.TYPES.beamline, parent__pk=spec['facility'])
        | Q(kind=Facility.TYPES.beamline, pk=spec['facility'])
        | Q(kind=Facility.TYPES.equipment, parent__pk=spec['facility'])
    )
    for facility in facilities:
        create_allocation(
            project, facility, cycle, shift_request=shift_request, shifts=shifts, procedure=spec.get('procedure'),
            justification=spec.get('justification'), scores=scores,
        )


def create_allocation(project, facility, cycle, procedure='', justification='', shifts=0, shift_request=0, scores=None):
    import numpy
    scores = scores or {}
    scores = {k: v for k, v in list(scores.items()) if not numpy.isnan(v)}
    alloc, created = models.Allocation.objects.get_or_create(project=project, beamline=facility, cycle=cycle)
    models.Allocation.objects.filter(pk=alloc.pk).update(
        shift_request=shift_request, shifts=shifts,
        procedure=procedure,
        justification=justification, scores=scores
    )
    return alloc
