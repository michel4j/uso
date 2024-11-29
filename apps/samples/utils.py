from . import models


def summarize_pictograms(hazards, types=None):
    pics = [pic.pk for hz in hazards.all() for pic in hz.pictograms.all()]
    if types:
        pics.extend([pic.pk for pic in types.all()])
    pictograms = models.Pictogram.objects.filter(pk__in=pics).distinct()
    remove_exclamation = pictograms.filter(code='GHS06').exists()
    remove_exclamation |= (hazards.filter(hazard__code='H334').exists() and pictograms.filter(code='GHS08').exists())
    remove_exclamation |= (hazards.filter(
        hazard__code__in=['H314', 'H315', 'H317', 'H318', 'H319']).exists() and pictograms.filter(
        code='GHS05').exists())
    if remove_exclamation:
        pictograms = pictograms.exclude(code='GHS07')

    return pictograms.exclude(code='000')
