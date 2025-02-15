import io

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse
from django.template import Context
from django.template.loader import get_template
from xhtml2pdf import pisa

from beamlines.models import Facility
from . import models
from proposals.models import ReviewType

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


def toInt(val, default=0):
    try:
        return int(val)
    except:
        return default


def create_project(submission):
    proposal = submission.proposal
    cycle = submission.cycle
    track = submission.track

    if submission.kind == submission.TYPES.user and track.acronym == 'RA':
        expiry = cycle.end_date
    elif submission.kind in [submission.TYPES.staff, submission.TYPES.purchased]:
        expiry = None
    else:
        expiry = cycle.start_date.replace(year=cycle.start_date.year + 2)
    submissions = submission.proposal.submissions.all()
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

    scores = submission.scores()
    # veto based on any non-facility score
    vetoed = any(USO_SCORE_VETO_FUNCTION(score) for key, score in scores.items() if key != 'facilities')

    # veto individual facilities
    bl_scores = {
        bl: score for bl, score in scores['facilities'].items()
        if not USO_SCORE_VETO_FUNCTION(score)
    }
    scores['facilities'] = bl_scores

    bl_specs = {
        entry['facility']: entry
        for entry in proposal.details.get('beamline_reqs', [])
    }

    if not vetoed and scores['facilities']:
        project, created = models.Project.objects.get_or_create(proposal=proposal, defaults=info)
        project.techniques.add(*submission.techniques.all())
        project.submissions.add(*submissions)
        facility_scores = scores.pop('facilities', {})
        del scores['technical']
        for bl, score in facility_scores.items():
            if not bl in bl_specs:
                continue
            spec = bl_specs[bl]
            alloc_scores = {**scores, 'technical': score}
            create_project_allocations(project, spec, cycle, scores=alloc_scores)
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
