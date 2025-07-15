from __future__ import annotations

import datetime
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from beamlines.models import Facility
from proposals.models import ReviewType, ReviewCycle
from . import models

USO_SAFETY_REVIEWS = getattr(settings, "USO_SAFETY_REVIEWS", [])
USO_SAFETY_APPROVAL = getattr(settings, "USO_SAFETY_APPROVAL", "approval")


def to_int(value: Any, default: int = 0) -> int:
    """
    Convert a value to an integer, returning a default value if conversion fails.
    :param value:  The value to convert to an integer
    :param default: The default value to return if conversion fails, defaults to 0
    """
    try:
        return int(value)
    except ValueError:
        return default


def calculate_end_date(start_date, duration) -> datetime.date:
    """
    Calculate the end date of a project based on the start date and duration in 6-month increments.
    :param start_date:
    :param duration: Number of 6-month increments to add to the start date
    :return:
    """
    year = start_date.year
    year_offset, month_offset = divmod(start_date.month - 1 + duration * 6, 12)
    end_year = year + year_offset
    end_month = 1 + month_offset
    return start_date.replace(year=end_year, month=end_month)


def summarize_scores(scores: dict) -> tuple[float, dict]:
    """
    Takes a dictionary mapping review stages to score information and returns a tuple containing
    the average score and a dictionary with the average score for each stage, keyed by the stage name.

    :param scores: dictionary mapping review stages to score information, score information should be a dictionary
    containing 'score_avg' for example {<ReviewStage>: {'score_avg': 2.5, ...} ...}. This function is compatible
    with entries returned by `Submission.get_facility_scores()`.
    """

    import numpy
    if not scores:
        return 0.0, {}

    score_data = numpy.array(
        [
            (stage.kind.code, details['score_avg'], stage.weight)
            for stage, details in scores.items()
        ], dtype=numpy.dtype([('stage', 'U64'), ('average', 'f4'), ('weight', 'f4')])
    )

    # Calculate the average score weighted by the stage weight
    weighted_avg = 0.0
    if not numpy.isclose(sum(score_data['weight']), 0):
        weighted_avg = numpy.average(score_data['average'], weights=score_data['weight'])

    # Create a dictionary with the average score for each stage
    stage_scores = {
        stage: float(average) for stage, average, weight in score_data
        if weight > 0.0
    }

    return float(weighted_avg), stage_scores


def create_project(submission) -> models.Project | None:
    """
    Create a project from approved submissions.
    :param submission: Submission instance to create a project from
    :return: Project instance if created, None otherwise
    """

    if not submission.approved:
        # If the submission is not approved, do not create a project
        return None

    proposal = submission.proposal
    cycle = submission.cycle
    track = submission.track
    expiry = calculate_end_date(cycle.end_date, track.duration - 1)
    info = {
        'pool': submission.pool,
        'spokesperson': proposal.spokesperson,
        'delegate': proposal.get_delegate(),
        'leader': proposal.get_leader(),
        'title': proposal.title,
        'cycle': cycle,
        'start_date': cycle.start_date,
        'end_date': expiry,
        'details': {
            'team_members': proposal.get_members(),
            'invoice_address': proposal.details.get('invoice_address', {})
        }
    }

    # get passing facility scores and corresponding requests
    passing_facilities = submission.get_facility_scores(passing_only=True)
    passing_requests = {
        facility: details
        for facility, details in submission.get_requests().items()
        if facility in passing_facilities
    }

    if passing_requests:
        # create the project if needed (only one per proposal), and allocations
        project, created = models.Project.objects.get_or_create(proposal=proposal, defaults=info)
        for facility, details in passing_requests.items():
            project.techniques.add(*details['techniques'].all())
            create_allocation_tree(
                project, facility, cycle, specs=details, shift_request=details.get('shifts', 0),
                scores=passing_facilities[facility]
            )

        project.submissions.add(submission)
        project.refresh_team()

        # create materials
        document = submission.get_document()
        material, created = models.Material.objects.get_or_create(
            project=project, defaults={
                'procedure': document['safety']['handling'],
                'waste': document['safety']['waste'],
                'disposal': document['safety']['disposal'],
                'equipment': document['safety']['equipment'],
            }
        )

        # add samples to the material
        for sample in document['safety']['samples']:
            models.ProjectSample.objects.get_or_create(
                material=material, sample_id=sample['sample'],
                defaults={'quantity': sample.get('quantity', '')}
            )

        # Create MaterialReviews
        # FIXME: This should be done in a signal or background task to allow for customization
        approval_type = ReviewType.objects.get(code=USO_SAFETY_APPROVAL)
        if approval_type:
            material.reviews.get_or_create(
                type=approval_type, form_type=approval_type.form_type, defaults={
                    'cycle': cycle, 'state': models.Review.STATES.open, 'role': approval_type.role
                }
            )
        return project
    return None


def create_allocation_tree(
        project: models.Project,
        facility: Facility,
        cycle: ReviewCycle,
        specs: dict = None,
        shifts: int = 0,
        shift_request: int = 0,
        scores: dict = None
) -> list[models.Allocation]:
    """
    Create facility allocation objects for a project based on the provided specifications. Takes
    into account the facility type and creates allocations for all relevant sub-facilities.
    :param project: Target project for the allocation
    :param facility: the facility to allocate
    :param cycle: Review cycle for the allocation
    :param specs: Specification dictionary containing justification and experimental procedure information
    :param shifts: Number of shifts allocated to the project, defaults to 0
    :param shift_request: Requested shifts for the allocation, defaults to 0
    :param scores: Review scores for this facility, defaults to None
    """

    specs = specs or {}
    shift_request = shift_request if shift_request is not None else shifts

    # Select facilities based on their type and parent-child relationships.
    # Allocation objects will be created for beamlines and equipment that are children
    # of the given facility or the facility itself if it is a beamline
    facilities = Facility.objects.filter(
        Q(kind__in=[Facility.TYPES.beamline, Facility.TYPES.equipment], parent__pk=facility.pk) |
        Q(kind=Facility.TYPES.beamline, pk=facility.pk)
    )
    created = []
    for facility in facilities:
        alloc = create_allocation(
            project, facility, cycle, specs=specs, shifts=shifts,
            shift_request=shift_request, scores=scores,
        )
        if alloc:
            created.append(alloc)
    return created


def create_allocation(
        project: models.Project,
        facility: Facility,
        cycle: ReviewCycle,
        specs: dict = None,
        shifts: int = 0,
        shift_request: int = 0,
        scores: dict = None
) -> models.Allocation:
    """
    Create a single allocation objects for a project.
    :param project: Target project for the allocation
    :param facility: the facility to allocate
    :param cycle: Review cycle for the allocation
    :param specs: Specification dictionary containing justification and experimental procedure information
    :param shifts: Number of shifts allocated to the project, defaults to 0
    :param shift_request: Requested shifts for the allocation, defaults to 0
    :param scores: Review scores for this facility, defaults to None
    """

    if scores:
        overall_score, scores = summarize_scores(scores)
    else:
        overall_score, scores = 0.0, {}

    alloc, created = models.Allocation.objects.get_or_create(project=project, beamline=facility, cycle=cycle)
    models.Allocation.objects.filter(pk=alloc.pk).update(
        shift_request=shift_request, shifts=shifts,
        procedure=specs.get('procedure'),
        justification=specs.get('justification'),
        score=overall_score,
        scores=scores,
        modified=timezone.localtime(timezone.now())
    )
    return alloc
