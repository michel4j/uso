import io
from typing import Any

from django.conf import settings
from django.db.models import F, Q, Avg
from django.http import HttpResponse
from django.template import Context
from django.template.loader import get_template
from xhtml2pdf import pisa

from beamlines.models import Facility
from proposals.models import ReviewType
from . import models

USO_SCORE_VETO_FUNCTION = getattr(settings, "USO_SCORE_VETO_FUNCTION", lambda score: score > 4)
USO_SAFETY_REVIEWS = getattr(settings, "USO_SAFETY_REVIEWS", [])
USO_SAFETY_APPROVAL = getattr(settings, "USO_SAFETY_APPROVAL", "approval")


def render_to_pdf(template_src, context_dict):
    template = get_template(template_src)
    context = Context(context_dict)
    html = template.render(context)
    result = io.StringIO()

    pdf = pisa.pisaDocument(io.StringIO(html.encode("ISO-8859-1")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return HttpResponse(f'We had some errors<pre>{html}</pre>')


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

    if submission.kind == submission.TYPES.user:
        expiry = calculate_end_date(cycle.end_date, track.duration - 1)
    else:
        expiry = None

    info = {
        'proposal': proposal,
        'kind': submission.kind,
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

    scores = dict(
        submission.reviews.complete().values('stage').order_by('stage').annotate(
            score=Avg('score')
        ).values_list('stage__kind__code', 'score')
    )
    passes_review = False
    check_facilities = False
    valid_facilities = set()
    for stage in track.stages.all():
        stage_code = stage.kind.code
        if stage.kind.per_facility:
            check_facilities = True  # check passage for each facility independently
            facility_scoring = submission.reviews.complete().filter(stage=stage).annotate(
                facility=F('details__facility')
            ).values('facility').annotate(
                score=Avg('score')
            ).values_list('facility', 'score')

            if stage.kind.low_better:
                stage_scores = dict(facility_scoring.filter(score__lte=stage.pass_score))
            else:
                stage_scores = dict(facility_scoring.filter(score__gte=stage.pass_score))

            passes_review = len(stage_scores) > 0
            if passes_review and stage.blocks:
                valid_facilities = set(stage_scores.keys())  # only these facilities can be valid
            elif passes_review:
                valid_facilities |= set(stage_scores.keys())  # add any valid ones from this stage to the set
            scores[stage_code] = stage_scores
        else:
            score = scores[stage_code]
            passes_review = (
                score <= stage.pass_score
                if stage.kind.low_better else
                score >= stage.pass_score
            )

        if not passes_review and stage.blocks:
            break

    if passes_review:
        requirements = {
            entry['facility']: entry
            for entry in proposal.details.get('beamline_reqs', [])
            if (to_int(entry['facility']) in valid_facilities or not check_facilities)
        }
        project, created = models.Project.objects.get_or_create(proposal=proposal, defaults=info)
        project.techniques.add(*submission.techniques.all())
        project.submissions.add(submission)
        for facility, spec in requirements.items():
            scores = compress_scores(scores, facility)
            create_project_allocations(project, spec, cycle, scores=scores)

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
