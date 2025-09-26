

from beamlines.models import Facility
from django.db import models
from django.db.models import F
from django.utils.translation import gettext as _
from django.utils import timezone
from misc.functions import Year
from model_utils import Choices
from model_utils.models import TimeStampedModel
from django.conf import settings


from misc.models import ActivityLog

User = getattr(settings, "AUTH_USER_MODEL")


class FundingSource(TimeStampedModel):
    name = models.CharField(max_length=255)
    acronym = models.CharField(max_length=255, blank=True, null=True)
    location = models.CharField(max_length=50, blank=True, null=True)
    doi = models.CharField(max_length=50, unique=True)
    parent = models.ForeignKey("self", blank=True, null=True, related_name="children", on_delete=models.SET_NULL)

    def __str__(self):
        return self.name + (f' ({self.acronym})' if self.acronym else "")

    def html_display(self):
        return f'{self}, {self.location}'


class FocusArea(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class SubjectArea(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    code = models.IntegerField(blank=True, null=True)
    category = models.ForeignKey("SubjectArea", blank=True, null=True, related_name="sub_areas", on_delete=models.SET_NULL)
    focus_area = models.ForeignKey(FocusArea, related_name="topics", blank=True, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name


class PublicationTag(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()

    def __str__(self):
        return self.name


class PublicationManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().annotate(year=F('date__year'))


class Journal(TimeStampedModel):
    title = models.TextField()
    short_name = models.TextField(max_length=255, blank=True, null=True)
    issn = models.CharField("ISSN", max_length=50, unique=True, null=True, blank=True)
    codes = models.JSONField('ISSN Codes', default=list, blank=True, null=True)
    publisher = models.CharField(max_length=100, blank=True, null=True)
    topics = models.ManyToManyField(SubjectArea, related_name='journals', blank=True)

    def __str__(self):
        return self.title


def default_year() -> int:
    """
    Returns the current year as an integer.
    """
    return timezone.localtime(timezone.now()).year


class JournalMetric(TimeStampedModel):
    journal = models.ForeignKey(Journal, related_name='metrics', on_delete=models.CASCADE)
    sjr_rank = models.FloatField("SJR-Rank", default=0.0, null=True)
    sjr_quartile = models.SmallIntegerField("SJR-Quartile", default=4, null=True)
    impact_factor = models.FloatField("Impact Factor", default=0.0, null=True)
    h_index = models.IntegerField("H-Index", default=1.0, null=True)
    year = models.IntegerField("Year", default=default_year)

    class Meta:
        unique_together = ('journal', 'year')

    def __str__(self):
        return f"{self.journal} > {self.year}"


class Publication(TimeStampedModel):
    class TYPES(models.TextChoices):
        article = 'article', _('Peer-Reviewed Article')
        proceeding = 'proceeding', _('Conference Proceeding')
        phd_thesis = 'phd_thesis', _('Doctoral Thesis')
        msc_thesis = 'msc_thesis', _('Masters Thesis')
        magazine = 'magazine', _('Magazine Article')
        chapter = 'chapter', _('Book Chapter')
        book = 'book', _('Book')
        pdb = 'pdb', _('PDB Deposition')
        patent = 'patent', _('Patent')

    date = models.DateField(_('Published'))
    authors = models.JSONField(_('Author List'), blank=True, null=True, default=list)

    title = models.TextField()
    main_title = models.TextField(blank=True, null=True)
    code = models.CharField(max_length=255, null=True)
    keywords = models.JSONField(_('Keyword List'), blank=True, null=True, default=list)
    kind = models.CharField(_('Type'), choices=TYPES.choices, default=TYPES.article, max_length=20)

    editors = models.TextField(blank=True, null=True)
    publisher = models.CharField(max_length=100, blank=True, null=True)
    address = models.CharField(max_length=50, blank=True, null=True)
    journal = models.ForeignKey(Journal, related_name='articles', on_delete=models.PROTECT, null=True)
    journal_metric = models.ForeignKey(JournalMetric, related_name='articles', on_delete=models.SET_NULL, null=True, blank=True)
    volume = models.CharField(max_length=100, blank=True, null=True)
    edition = models.CharField(max_length=20, blank=True, null=True)
    issue = models.CharField(max_length=20, blank=True, null=True)
    pages = models.CharField(max_length=20, blank=True, null=True)

    reviewed = models.BooleanField(_('Reviewed'), default=False)
    tags = models.ManyToManyField(PublicationTag, related_name='publications', verbose_name='Tags', blank=True)
    areas = models.ManyToManyField(SubjectArea, related_name="publications", verbose_name="Subject Areas", blank=True)
    reference = models.ForeignKey('Publication', related_name="pdbs", null=True, on_delete=models.SET_NULL)
    pdb_doi = models.CharField(max_length=100, blank=True, null=True, verbose_name="PDB DOI")

    notes = models.TextField(blank=True, null=True)
    affiliation = models.JSONField(default=dict)
    beamlines = models.ManyToManyField(Facility, related_name="publications", blank=True)
    users = models.ManyToManyField(User, related_name="publications", verbose_name="Users", blank=True)
    funders = models.ManyToManyField(FundingSource, related_name="publications", verbose_name="Funding Sources", blank=True)
    objects = PublicationManager()

    def is_owned_by(self, user):
        return user in self.users.all()

    @property
    def history(self):
        return ActivityLog.objects.filter(
            content_type__model='publication',
            object_id=self.id
        ).order_by('-created')

    def cite(self):
        parts = [f"{self.abbrev_authors()} ({self.date.year}). {self.title}"]
        issue = f'({self.issue})' if self.issue else ''
        pages = f', {self.pages}' if self.pages else ''
        volume = f'{self.volume}' if self.volume else ''
        address = f', {self.address}' if self.address else ''
        publisher = f'{self.publisher}{address}' if self.publisher else ''
        main_title = f'<em>{self.main_title}</em>' if self.main_title else ''
        edition = f'({self.edition})' if self.edition else ''
        editors = f"{self.editors} (Eds.)" if self.editors else ''
        supervisor = f"{self.editors} (Sup.) " if self.editors else ''

        if self.kind in [Publication.TYPES.article, Publication.TYPES.proceeding, Publication.TYPES.magazine]:
            if self.journal:
                parts.append(f"<em>{self.journal.title}</em> {volume}{issue}{pages}")
            else:
                parts.append(f"{publisher} {volume}{edition}{pages}")
        elif self.kind == Publication.TYPES.pdb:
            parts.append(f"Protein Data Bank")
        elif self.kind == Publication.TYPES.patent:
            parts.append(f"Patent")
        elif self.kind == Publication.TYPES.book:
            parts.append(f"{publisher}")
        elif self.kind == Publication.TYPES.msc_thesis:
            parts.append(f"Masters Thesis")
            parts.append(f"{supervisor}{publisher}")
        elif self.kind == Publication.TYPES.phd_thesis:
            parts.append('Doctoral Dissertation')
            parts.append(f"{supervisor}{publisher}")
        elif self.kind == Publication.TYPES.chapter:
            parts.append(f"In {editors}{main_title}{pages}, {publisher}")
        if self.code:
            parts.append(self.code)
        return '. '.join(parts)

    cite.sort_field = 'authors'
    cite.short_description = 'Publication'
    cite.allow_tags = True

    def facility_codes(self):
        return ', '.join([bl.acronym for bl in self.beamlines.distinct()])
    facility_codes.sort_field = 'beamlines__acronym'
    facility_codes.short_description = 'Facilities'

    @property
    def citation(self):
        return self.cite()

    @property
    def short_citation(self):
        cite = self.cite()
        if len(self.title) > 70:
            cite = cite.replace(self.title, self.title[:70] + ' ...')
        return cite

    def abbrev_authors(self):
        if len(self.authors) < 5:
            return "; ".join(self.authors)
        else:
            return "; ".join(self.authors[:5]) + " et al."

    def __str__(self):
        return "{0} ({1}). {2}".format(
            self.abbrev_authors(),
            self.date.year,
            self.title[:70] + (' ...' if len(self.title) > 70 else ''), )


class ArticleMetric(TimeStampedModel):
    publication = models.ForeignKey(Publication, related_name='metrics', on_delete=models.CASCADE)
    citations = models.IntegerField("Citations", default=0)
    mentions = models.IntegerField("Mentions", default=0)
    self_cites = models.IntegerField("Self-Citations", default=0)
    year = models.IntegerField("Year", default=default_year)

    class Meta:
        unique_together = ('publication', 'year')

    def __str__(self):
        return "{} > {}".format(self.publication, self.year)


Patent = Publication
Book = Publication
Article = Publication
PDBDeposition = Publication


def check_unique(title=None, authors=None, code=None):
    qf = None
    if title:
        qf = models.Q(title__icontains=title)
        if authors:
            qf &= models.Q(authors__icontains=authors)
    elif authors:
        qf = models.Q(authors__icontains=authors)
    if code:
        if not qf:
            qf = models.Q()
        qf |= models.Q(code__icontains=code)

    matches = qf and Publication.objects.filter(qf) or Publication.objects.none()
    return matches.count() and matches or matches.none()
