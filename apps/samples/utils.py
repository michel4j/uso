from . import models
from django.db.models import Case, When, BooleanField


def summarize_pictograms(hazards, extras=None, types=None):
    """
    Fetch the pictograms associated with hazards and types.
    :param hazards: QuerySet of hazards
    :param extras: QuerySet of additional hazards include will be annotated with the `extra` boolean field
    :param types: QuerySet of hazard types (optional)
    :return: QuerySet of distinct pictograms annotated with the `extra` boolean attribute based on their membership in
             hazards or extras.
    """

    main_pics = list(hazards.values_list('pictograms__pk', flat=True).distinct())
    extra_pics = [] if not extras else list(extras.values_list('pictograms__pk', flat=True).distinct())
    if types:
        main_pics.extend(list(types.values_list('pk', flat=True).distinct()))

    # pictograms = models.Pictogram.objects.filter(pk__in=main_pics).distinct()
    # remove_exclamation = pictograms.filter(code='GHS06').exists()
    # remove_exclamation |= (hazards.filter(hazard__code='H334').exists() and pictograms.filter(code='GHS08').exists())
    # remove_exclamation |= (hazards.filter(
    #     hazard__code__in=['H314', 'H315', 'H317', 'H318', 'H319']).exists() and pictograms.filter(
    #     code='GHS05').exists())
    # if remove_exclamation:
    #     pictograms = pictograms.exclude(code='GHS07')

    return models.Pictogram.objects.filter(pk__in=main_pics + extra_pics).annotate(
        extra=Case(
            When(pk__in=main_pics, then=False),
            default=True,
            output_field=BooleanField()
        )
    ).exclude(code='000')

