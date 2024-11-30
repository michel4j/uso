import io

from django.db.models import Q
from django.http import HttpResponse
from django.template import Context
from django.template.loader import get_template
from xhtml2pdf import pisa

from . import models
from beamlines.models import Facility
from proposals.utils import conv_score


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
            'invoice_address': proposal.details.get('invoice_address', {})}
    }

    scores = {'score_{}'.format(k): float(v) for k, v in list(submission.scores().items()) if v}
    scores['score_merit'] = submission.score()
    technical_scores = {
        toInt(r.details.get('requirements', {}).get('facility', 0)): conv_score(r.details.get('suitability'))
        for r in submission.reviews.technical().complete()
    }

    # only beamlines where technical review was completed and technical score is better than or equal to 4
    bl_scores = [x for x in [
        (technical_scores.get(int(bl['facility']), 0.0), bl)
        for bl in proposal.details['beamline_reqs']
    ] if 0 < x[0] <= 4]

    if bl_scores and scores.get('score_merit', 0.0) <= 4:
        project, created = models.Project.objects.get_or_create(proposal=proposal, defaults=info)
        project.techniques.add(*submission.techniques.all())
        project.submissions.add(*submissions)
        for tech_score, bl in bl_scores:
            scores.update(score_technical=tech_score)
            shift_request = bl.get('shifts') or 0
            create_project_allocations(project, bl, cycle, scores=scores, shift_request=shift_request)
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
        from dynforms.models import FormType
        approval_form = FormType.objects.all().filter(code='safety-approval')
        approval, created = material.reviews.get_or_create(
            kind='approval', form_type=approval_form, defaults={
                'cycle': cycle, 'state': models.Review.STATES.open, 'role': "safety-approver"
            }
        )

        if material.needs_ethics():
            ethics_form = FormType.objects.all().filter(code='ethics_review')
            ethics, created = material.reviews.get_or_create(
                kind="ethics", form_type=ethics_form, defaults={
                    'cycle': cycle, 'state': models.Review.STATES.open, 'role': "ethics-approver"
                }
            )


def create_project_allocations(project, spec, cycle, shifts=0, shift_request=0, scores={}):
    facilities = Facility.objects.filter(
        Q(kind=Facility.TYPES.beamline, parent__pk=spec['facility'])
        | Q(kind=Facility.TYPES.beamline, pk=spec['facility'])
        | Q(kind=Facility.TYPES.equipment, parent__pk=spec['facility'])
    )
    for facility in facilities:
        # print (project, facility, cycle, shift_request, shifts, spec.get('procedure'))
        create_allocation(
            project, facility, cycle, shift_request=shift_request, shifts=shifts, procedure=spec.get('procedure'),
            justification=spec.get('justification'), scores=scores
        )


def create_allocation(project, facility, cycle, procedure='', justification='', shifts=0, shift_request=0, scores={}):
    import numpy
    scores = {k: v for k, v in list(scores.items()) if not numpy.isnan(v)}
    alloc, created = models.Allocation.objects.get_or_create(project=project, beamline=facility, cycle=cycle)
    models.Allocation.objects.filter(pk=alloc.pk).update(shift_request=shift_request, shifts=shifts,
                                                         procedure=procedure,
                                                         justification=justification, **scores)
    return alloc
