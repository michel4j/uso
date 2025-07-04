from collections import defaultdict

from django import template
from django.contrib.staticfiles.storage import staticfiles_storage
from django.db.models import Q, When, BooleanField, Value, Case

from samples import models
from samples import utils

register = template.Library()


@register.simple_tag(takes_context=True)
def get_sample_types(context):
    groups = [(v[0], [(x[0], x[-1]) for x in v[1]]) for v in models.Sample.TYPES if not isinstance(v[-1], str)]
    groups += [
        ('Others Types', [(v[0], v[-1]) for v in models.Sample.TYPES if isinstance(v[-1], str) and v[-1] != ""])]
    return groups


@register.simple_tag(takes_context=True)
def get_waste_types(context):
    groups = [(v[0], [(x[0], x[-1]) for x in v[1]]) for v in models.WASTE_TYPES if not isinstance(v[-1], str)]
    return groups


@register.simple_tag(takes_context=True)
def get_safety_controls(context, data=None):
    data = [] if not data else data
    controls = models.SafetyControl.objects.filter(active=True)
    if data and isinstance(data, list):
        controls = controls.annotate(
            selected=Case(When(pk__in=data, then=Value(1)), default=Value(0), output_field=BooleanField()))

    groups = defaultdict(lambda: defaultdict(list))
    for c in controls.all():
        groups[c.get_kind_display()][c.get_category_display()].append(c)
    return {k: dict(v) for k, v in list(groups.items())}


@register.filter
def waste_label(waste):
    return models.WASTE_TYPES[waste]


@register.simple_tag(takes_context=True)
def get_pictograms(context):
    return models.Pictogram.objects.all()


@register.simple_tag()
def pictogram_url(pictogram):
    return staticfiles_storage.url(f'samples/pictograms/{pictogram.code}.svg')


@register.inclusion_tag('samples/pictograms.html')
def show_pictograms(hazards, extras=None, types=None):
    pictograms = utils.summarize_pictograms(hazards, extras=extras, types=types)
    return {'pictograms': pictograms.all()}


@register.simple_tag(takes_context=True)
def precaution_text(context, precaution):
    return precaution.text


@register.simple_tag(takes_context=True)
def precaution_keyword(context, precaution):
    sample = context['sample']
    data = context['data']
    try:
        sample_info = {d['sample']: d for d in data}
        sample_keywords = sample_info[sample.pk].get('keywords', {})
        return sample_keywords.get(precaution.code, '')
    except:
        return ''


@register.simple_tag(takes_context=True)
def get_precaution_keywords(context):
    """
    Returns a dictionary of precaution codes and their corresponding keywords for the given precautions.
    """
    sample = context.get('sample')
    data = context.get('data', [])

    if not sample or not data:
        return {}

    try:
        sample_info = {d['sample']: d for d in data}
        return sample_info[sample.pk].get('keywords', {})
    except (KeyError, TypeError):
        return {}


@register.simple_tag(takes_context=True)
def get_user_samples(context, data=None):
    data = [] if not data else data
    user = context['user']
    if user.is_authenticated:
        try:
            _data = {int(v['sample']): v['quantity'] for v in data}
            _all = {s.pk: s for s in
                    models.Sample.objects.filter(Q(owner=user.pk) | Q(pk__in=list(_data.keys()))).distinct()}
            samples = {
                'selected': [(_all.get(k), v) for k, v in list(_data.items()) if k in _all],
                'all': [(s, k in list(_data.keys())) for k, s in list(_all.items())]
            }
        except (ValueError, TypeError):
            samples = {}
    else:
        samples = {}
    return samples


@register.simple_tag(takes_context=True)
def get_material_samples(context, data=None, material=None):
    if not material:
        return []

    sample_info = {}
    try:
        if isinstance(data, list):
            sample_info = {
                item['sample']: item
                for item in data
            }
    except (TypeError, KeyError):
        sample_info = {}

    try:
        samples = material.project_samples.order_by('sample__kind')
        sample_list = [
            (
                s.sample,
                s.quantity,
                s.sample.hazards.all(),  # sample_hazards
                models.Hazard.objects.filter(pk__in=sample_info.get(s.sample.pk, {}).get('hazards', [])),
                # review_hazards
                sample_info.get(s.sample.pk, {}).get('rejected', False),  # rejected
                sample_info.get(s.sample.pk, {}).get('permissions', {}) or s.sample.permissions(),  # permissions
            )
            for s in samples.all()
        ]
    except (ValueError, TypeError, KeyError):
        sample_list = []
    return sample_list


@register.simple_tag(takes_context=True)
def get_safety_samples(context, data):
    """
    Returns a list of dictionaries containing sample information for each sample's safety review.
    :param context: template context
    :param data: sample data to be processed, if any
    :return:
    """
    data = [] if not data else data
    review = context.get('object')
    invalid = (
            not review or
            not hasattr(review, 'reference') or
            not hasattr(review.reference, 'project_samples') or
            not isinstance(data, list)
    )
    if invalid:
        return []

    # load sample_info with defaults from the sample
    material = review.reference
    sample_info = {
        mat_sample.sample.pk: {
            'sample': mat_sample.sample,
            'quantity': mat_sample.quantity,
            'expiry': mat_sample.expiry,
            'rejected': mat_sample.state == mat_sample.STATES.rejected,
            'hazards': mat_sample.sample.hazards.all(),
            'permissions': mat_sample.sample.permissions(),
            'precautions': mat_sample.sample.precautions(),
            'keywords': mat_sample.sample.details.get('keywords', {}),
        }
        for mat_sample in material.project_samples.filter().order_by('sample__kind')
    }

    try:
        # update sample_info with data from the review
        for rev_sample in data:
            pk = int(rev_sample['sample'])
            rev_sample['rejected'] = int(rev_sample.get('rejected', 0))

            for key in ['expiry', 'decision', 'permissions', 'keywords']:
                if key in rev_sample:
                    sample_info[pk][key] = rev_sample[key]

            if 'hazards' in rev_sample:
                sample_info[pk]['hazards'] = models.Hazard.objects.filter(pk__in=rev_sample['hazards'])
                sample_info[pk]['precautions'] = models.PStatement.objects.for_hazards(rev_sample['hazards'])

    except (ValueError, TypeError, KeyError):
        pass
    return sample_info.values()


@register.inclusion_tag('samples/fields/sample-safety.html', takes_context=True)
def sample_safety_review(context, sample_info: dict):
    """
    Renders the safety review template with the provided context and data.
    :param context: The template context
    :param sample_info: Information about the sample to be reviewed
    """

    return {
        'data': context.get('data'),
        'field': context.get('field'),
        **sample_info
    }


@register.inclusion_tag('samples/fields/sample-ethics.html', takes_context=True)
def sample_ethics_review(context, sample_info: dict):
    """
    Renders the safety review template with the provided context and data.
    :param context: The template context
    :param sample_info: Information about the sample to be reviewed
    """

    return {
        'data': context.get('data'),
        'field': context.get('field'),
        **sample_info
    }


@register.simple_tag(takes_context=True)
def get_samples(context, data=None):
    data = [] if not data else data
    quantities = {int(v['sample']): v['quantity'] for v in data if v}
    return [
        (s, quantities.get(s.pk))
        for s in models.Sample.objects.filter(pk__in=quantities.keys()).order_by('kind')
    ]


@register.simple_tag(takes_context=True)
def get_permissions(context, data=None):
    data = context.get('data', {}) if not data else data
    if not isinstance(data, dict):
        data = {}

    perms = [(p, data.get(p.code)) for p in models.SafetyPermission.objects.filter(review=True)]
    return {
        'permissions': perms,
        'requirements': {
            'any': 'Require any',
            'all': 'Require all',
            'optional': 'Recommend',
            '': 'Not Required',
        }
    }

@register.filter
def group_sample_choices(choices, defaults):
    if defaults == '':
        defaults = []
    ch = [(v, (v[0] in defaults)) for v in choices]
    return ch


@register.filter
def fetch_hazards(hz_ids):
    if hz_ids:
        return models.Pictogram.objects.filter(pk__in=hz_ids).exclude(pk=15)
    else:
        return []


@register.filter
def hz_transforms(pos, length=0, vertical=False):
    if vertical:
        trans = 'translate({1}%, {0}%)'.format(-(pos + 1) * 50, (pos % 2) * 50)
    else:
        trans = 'translate({0}%, {1}%)'.format(-(pos + 1) * 50, (pos % 2) * 50)
    return "position: absolute; transform: {0};".format(trans)


@register.filter
def format_pstatement(prec, sample):
    return prec.text.format("<strong>{}</strong>".format(sample.details.get('keywords', {}).get(str(prec.code), "")))


@register.simple_tag(takes_context=True)
def update_saved_hazards(context):
    saved_hazards = context.get('saved_hazards', [])
    if not saved_hazards:
        if 'data' in context:
            saved_hazards = context['data'].get('saved_hazards', [])
            saved_hazards = list(map(int, saved_hazards))
    print("Saved Hazards:", saved_hazards)
    return saved_hazards


@register.simple_tag(takes_context=True)
def unpack(context, data: dict):
    context.update(data)
    return ''


@register.filter
def query_ids(queryset):
    """
    Returns a list of IDs from a queryset.
    :param queryset: A Django queryset
    :return: List of IDs
    """
    return [obj.pk for obj in queryset] if queryset else []
