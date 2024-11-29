

from django.conf import settings
from django.db import models
from django.utils.translation import gettext as _
from model_utils import Choices
from model_utils.models import TimeStampedModel

from . import utils
from misc.models import GenericContentMixin

User = getattr(settings, "AUTH_USER_MODEL")

SIGNALS = Choices(
    ('warning', _('Warning')),
    ('danger', _('Danger')),
)

WASTE_TYPES = Choices(
    (_('Biological Wastes'), [
        ('bio_solids', _('Biological petri dishes, pipette tips, etc.')),
        ('bio_liquids', _('Biological liquids, cultures, etc')),
        ('bio_sharps', _('Biological syringes, blades, glass etc.')),
        ('bio_tissues', _('Biological, tissues, etc.')),
    ]),
    (_('Others'), [
        ('radioactive', _('Radioactive Waste')),
        ('chemical', _('Solid/Liquid Chemical Waste')),
        ('hazardous_gas', _('Hazardous gases')),
        ('nonhazardous', _('Non-Hazardous Waste')),
    ]),
)


class CodeManager(models.Manager):
    def get_by_natural_key(self, code):
        return self.get(code=code)


class HStatement(TimeStampedModel):
    code = models.CharField(max_length=20, unique=True, db_index=True)
    text = models.CharField(max_length=255)
    objects = CodeManager()

    def __str__(self):
        return "{}: {}".format(self.code, self.text)

    def natural_key(self):
        return self.code,  # tuple


class PStatement(TimeStampedModel):
    code = models.CharField(max_length=20, unique=True, db_index=True)
    text = models.CharField(max_length=255)
    objects = CodeManager()

    def __str__(self):
        return "{}: {}".format(self.code, self.text)

    def natural_key(self):
        return self.code,  # tuple


class Pictogram(TimeStampedModel):
    name = models.CharField(max_length=100)
    description = models.TextField()
    code = models.CharField(max_length=20)
    objects = CodeManager()

    def __str__(self):
        return self.name

    def natural_key(self):
        return self.code,


class HazardManager(models.Manager):
    def get_by_natural_key(self, signal, hazard):
        return self.get(signal=signal, hazard__code=hazard)


# initial source of information Sigma-Aldrich GHS Poster GHS_EU_Poster.pdf
class Hazard(TimeStampedModel):
    signal = models.CharField(max_length=10, choices=SIGNALS, blank=True)
    hazard = models.ForeignKey(HStatement, on_delete=models.CASCADE)
    pictograms = models.ManyToManyField(Pictogram, related_name='hazards')
    precautions = models.ManyToManyField(PStatement, related_name='hazards')
    permissions = models.ManyToManyField('SafetyPermission', related_name='hazards', blank=True)
    description = models.TextField(blank=True)
    objects = HazardManager()

    def __str__(self):
        return "{}{}".format('{}: '.format(self.get_signal_display()) if self.signal else '', self.hazard.text)

    def natural_key(self):
        return (self.signal,) + self.hazard.natural_key()

    class Meta:
        unique_together = (('signal', 'hazard'),)


class Sample(TimeStampedModel):
    TYPES = Choices(
        ('', _('')),
        ('chemical', _('Chemical')),
        ('macromolecule', _('Macromolecules')),
        ('geologic', _('Soil, rocks or geologic')),
        (_('Human'), [
            ('human_subject', _('Human Subject')),
            ('human_tissue_alive', _('Human Tissue/Fluid (Living)')),
            ('human_tissue', _('Human Tissue/Fluid')),
            ('human_other', _('Other Human Material')),
        ]),
        (_('Animal'), [
            ('live_animal', _('Live Animal')),
            ('animal_tissue', _('Non-Invasive Animal Tissue/Fluid (Cat A)')),
            ('animal_tissue_invasive', _('Invasive Animal Tissue/Fluid (Cat B+)')),
            ('animal_other', _('Other Animal Material')),
        ]),
        (_('Other Biological'), [
            ('plant', _('Plant or Algae')),
            ('microbe', _('Bacteria, Protozoa or Virus')),
            ('fungi', _('Fungi')),
            ('gmo', _('Genetically Modified Organism')),
            ('bio_other', _('Other biological')),
        ]),
        ('other', _('Other')),
    )
    STATES = Choices(
        ('', _('')),
        ('solid', _('Solid')),
        ('liquid', _('Liquid')),
        ('crystal', _('Crystal')),
        ('gas', _('Gas')),
        ('frozen', _('Frozen')),
        ('suspension', _('Suspension')),
        ('nano', _('Nano-Material')),
        ('fixed', _('Fixed')),
        ('sealed', _('Sealed Radioactive Source')),
        ('other', _('Other State')),
    )
    ETHICS_TYPES = [
        "human_subject", "human_tissue_alive", "human_tissue", "human_other",
        "live_animal", "animal_tissue", "animal_tissue_invasive", "animal_other"
    ]
    owner = models.ForeignKey(User, null=True, related_name='samples', on_delete=models.SET_NULL)
    name = models.CharField("Full Name", max_length=255)
    source = models.CharField("Source of Material", max_length=100, null=True, blank=True)
    extra = models.CharField("Additional Information", max_length=100, null=True, blank=True)
    kind = models.CharField("Type", max_length=100, choices=TYPES, default=None)
    state = models.CharField(max_length=100, choices=STATES, default=None)
    hazard_types = models.ManyToManyField(Pictogram, verbose_name="Hazard Types", related_name='samples')
    hazards = models.ManyToManyField(Hazard, verbose_name="Hazards", related_name='samples')
    description = models.TextField(null=True, blank=True)
    is_editable = models.BooleanField(default=True)

    details = models.JSONField(default=dict, null=True, blank=True, editable=False)

    def __str__(self):
        return self.name

    def signal(self):
        for w in ['danger', 'warning']:
            if w in self.hazards.values_list('signal', flat=True).distinct():
                return w
        return ""

    def pictograms(self):
        if self.is_editable:
            return utils.summarize_pictograms(self.hazards, self.hazard_types)
        else:
            return utils.summarize_pictograms(self.hazards)

    def precautions(self):
        precautions = PStatement.objects.filter(
            pk__in=[p.pk for hz in self.hazards.all() for p in hz.precautions.all()]).order_by('code')
        remove_statements = []
        for p in precautions.filter(code__contains="+"):
            remove_statements.append(p.code.split("+"))
        return precautions.exclude(code__in=[code for codes in remove_statements for code in codes]).distinct()

    def permissions(self):
        perms = {
            perm: 'all'
            for perm in
            self.hazards.filter(permissions__isnull=False).values_list('permissions__code', flat=True)
        }
        perms.update(self.details.get('permissions', {}))
        return perms

    def precautions_text(self):
        keywords = self.details.get('keywords', {})
        txt = ""
        for p in self.precautions():
            p_txt = p.text.format(keywords.get(p.code, '{}'))
            txt += "{}.  ".format(p_txt)
        return txt

    def hazards_text(self):
        txt = ""
        for hz in self.hazards.all():
            txt += "{}.  ".format(hz.hazard.text)
        return txt


class HazardousSubstance(models.Model):
    name = models.CharField("Name", max_length=255, unique=True)
    description = models.TextField()
    hazards = models.ManyToManyField(Hazard, verbose_name="Hazards", related_name='substances')

    def __str__(self):
        return self.name


class SafetyPermission(TimeStampedModel):
    code = models.CharField(max_length=50)
    description = models.CharField(max_length=100, blank=True, null=True)
    review = models.BooleanField(_('Show in Review'), default=True)

    def __str__(self):
        return self.description


class SafetyControl(TimeStampedModel):
    TYPES = Choices(
        ('team', _('Team Requirements')),
        ('guide', _('Safety Instructions')),
        ('ppe', _('Personal Protection Equipment')),
        ('form', _('Forms')),
        ('delivery', _('Material Delivery/Removal')),
        ('signage', _('Signage and Permits')),
        ('disposal', _('Disposal and Storage')),
    )
    GROUPS = Choices(
        ('engineering', _('Engineering Controls')),
        ('ppe', _('Personal Protection Equipment')),
        ('inspection', _('Equipment Inspection')),
        ('administrative', _('Administrative Controls')),
        ('other', _('Other Controls')),
    )
    name = models.CharField(max_length=250)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=TYPES, default=TYPES.guide)
    kind = models.CharField(max_length=20, choices=GROUPS, default=GROUPS.engineering)
    active = models.BooleanField(_('Show in Review'), default=True)

    def __str__(self):
        return self.name


class UserRequirement(GenericContentMixin, TimeStampedModel):
    TYPES = Choices(
        ('any', _('Anyone')),
        ('all', _('Everyone')),
        ('optional', _('Optional')),
    )
    permission = models.ForeignKey(SafetyPermission, related_name='requirements', on_delete=models.CASCADE)
    kind = models.CharField(choices=TYPES, max_length=20, verbose_name="Type")

    def __str__(self):
        return "{} - {}".format(self.kind, self.permission)
