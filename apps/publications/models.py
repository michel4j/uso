

from beamlines.models import Facility
from django.db import models
from django.db.models import F
from misc.fields import StringListField
from django.utils.translation import gettext as _
from misc.functions import Year
from model_utils import Choices
from model_utils.models import TimeStampedModel
from model_utils.managers import InheritanceManager
from django.conf import settings
import re

User = getattr(settings, "AUTH_USER_MODEL")


class FundingSource(TimeStampedModel):
    name = models.CharField(max_length=255)
    acronym = models.CharField(max_length=255)
    kind = models.CharField(_('Type'), max_length=50, blank=True, null=True)
    location = models.CharField(max_length=50, blank=True, null=True)
    doi = models.CharField(max_length=50)

    def __str__(self):
        return self.name + (' ({0})'.format(self.acronym) if self.acronym else "")

    def html_display(self):
        return '{}, {}'.format(self, self.location)


class SubjectArea(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    code = models.IntegerField(blank=True, null=True)
    category = models.ForeignKey("SubjectArea", blank=True, null=True, related_name="sub_areas", on_delete=models.SET_NULL)

    def __str__(self):
        return self.name


class PublicationTag(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()

    def __str__(self):
        return self.name


class PublicationManager(InheritanceManager):
    def get_queryset(self):
        return super().get_queryset().annotate(year=Year(F('date')))


class Journal(TimeStampedModel):
    TYPES = Choices(
        ('journal', _('Peer-Reviewed Journal')),
        ('proceedings', _('Conference Proceedings')),
        ('nonrefereed', _('Non-Refereed Journal')),
        ('bookseries', _('Book Series')),
        ('book', _('Book')),
    )
    title = models.CharField(max_length=255)
    issn = models.CharField("ISSN", max_length=50, unique=True)
    publisher = models.CharField(max_length=100, blank=True, null=True)
    kind = models.CharField(max_length=100, blank=True, null=True)
    sjr = models.FloatField("SJR-Rank", default=0.0)
    ifactor = models.FloatField("Impact Factor", default=0.0)
    hindex = models.IntegerField("H-Index", default=1.0)
    score_date = models.DateField(null=True)

    def __str__(self):
        return self.title


class Publication(TimeStampedModel):
    TYPES = Choices(
        ('article', _('Peer-Reviewed Article')),
        ('proceeding', _('Conference Proceeding')),
        ('phd_thesis', _('Doctoral Thesis')),
        ('msc_thesis', _('Masters Thesis')),
        ('magazine', _('Magazine Article')),
        ('chapter', _('Book / Chapter')),
        ('pdb', _('PDB Deposition')),
        ('patent', _('Patent')))

    CATEGORIES = Choices(
        ('beamline', _('Beamline')),
        ('dataless', _('Staff, No CLS Data')),
        ('design', _('Beamline Design')),
        ('facility', _('Facility')),
    )
    authors = StringListField(_('Authors'))
    title = models.TextField()
    date = models.DateField(_('Published'))
    keywords = models.TextField(blank=True, null=True)
    beamlines = models.ManyToManyField(Facility, related_name="publications", blank=True)
    users = models.ManyToManyField(User, related_name="publications", verbose_name="CLS Users", blank=True)
    funders = models.ManyToManyField(FundingSource, related_name="publications", verbose_name="Funding Sources",
                                     blank=True)
    kind = models.CharField(_('Type'), choices=TYPES, default=TYPES.article, max_length=20)
    citations = models.IntegerField(default=0)
    reviewed = models.BooleanField(_('Reviewed'), default=False)
    category = models.CharField(_('Category'), choices=CATEGORIES, max_length=30, blank=True, null=True)
    tags = models.ManyToManyField(PublicationTag, related_name='publications', verbose_name='Tags', blank=True)
    areas = models.ManyToManyField(SubjectArea, related_name="publications", verbose_name="Subject Areas", blank=True)
    notes = models.TextField(blank=True, null=True)
    affiliation = models.JSONField(default=dict)
    history = models.JSONField(default=list, blank=True)
    objects = PublicationManager()

    def is_owned_by(self, user):
        return user in self.users.all()

    def description(self):
        return ""

    def cite(self):
        return f"{self.abbrev_authors()} ({self.date.year}). <em>{self.title}</em>."
    cite.sort_field = 'authors'
    cite.short_description = 'Publication'
    cite.allow_tags = True

    def facility_codes(self):
        return ', '.join([bl.acronym for bl in self.beamlines.distinct()])
    facility_codes.sort_field = 'beamlines__acronym'
    facility_codes.short_description = 'Facilities'

    @property
    def citation(self):
        return Publication.objects.get_subclass(id=self.id).cite()

    @property
    def short_citation(self):
        cite = Publication.objects.get_subclass(id=self.id).cite()
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


class Patent(Publication):
    code = models.CharField("Patent Number", max_length=30, null=True, unique=True)

    def description(self):
        return f"Patent Number {self.code}"

    def cite(self):
        return (
            f"{self.abbrev_authors()} ({self.date.year}). <em>{self.title}</em>. "
            "<span class='text-body-secondary'>Patent Number: <a target='blank' "
            f"href='https://www.google.com/patents/{self.code}'>{self.code}</a>.</span>"
        )

    cite.short_description = 'Patent'
    cite.allow_tags = True


class Book(Publication):
    TYPES = Choices(
        ('msc_thesis', 'Masters Thesis'),
        ('phd_thesis', 'Doctoral Thesis'),
        ('chapter', 'Book/Chapter'),
        ('proceeding', _('Conference Proceeding')),
    )
    code = models.CharField("ISBN or DOI", max_length=255, blank=True, null=True)
    main_title = models.CharField(max_length=255, blank=True, null=True)
    editor = models.TextField(blank=True, null=True)
    publisher = models.CharField(max_length=100, blank=True, null=True)
    edition = models.CharField(max_length=10, blank=True, null=True)
    address = models.CharField(max_length=50, blank=True, null=True)
    volume = models.CharField(max_length=100, blank=True, null=True)
    pages = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        verbose_name = 'Chapters/Books'
        verbose_name_plural = 'Chapters/Books'

    def description(self):
        return f"Published by {self.publisher}"

    def cite(self, full=False):
        authors = "; ".join(self.authors) if full else self.abbrev_authors()
        txt = "{0} ({1}). <em>{2}</em>. ".format(authors, self.date.year, self.title)
        if self.main_title:
            txt += 'In ' + (self.editor + '(Ed.), ' if self.editor else "") + self.main_title + ". "
        if self.editor and 'thesis' in self.kind:
            txt += 'Supervisor: {0}. '.format(self.editor)
        if self.address:
            txt += self.address + ": "
        txt += " {0}. ".format(self.publisher)
        if self.pages:
            txt += ", " + self.pages
        if self.code:
            if re.match(r'10.(\d+)/(\S+)', self.code):
                base = "https://dx.doi.org/{0}"
            elif re.match(r'^\d{12}[\d|X]$', self.code):
                base = "https://books.google.com/books?vid=ISBN{0}"
            elif self.reviewed:
                base = "{0}"
            else:
                base = None
            if base:
                txt += ' <span class="text-body-secondary"><a target="blank" href="{0}">{1}</a>.</span>'.format(
                    base.format(self.code), self.code)
        else:
            txt += "."
        return txt

    cite.short_description = 'Book/Chapter'
    cite.allow_tags = True


class Article(Publication):
    TYPES = Choices(
        ('article', 'Journal Article'),
        ('proceeding', 'Conference Proceeding')
    )
    code = models.CharField("DOI", max_length=50, unique=True, null=True)
    journal = models.ForeignKey(Journal, related_name='articles', on_delete=models.CASCADE)
    volume = models.CharField(max_length=100, blank=True, null=True)
    number = models.CharField(max_length=20, blank=True, null=True)
    pages = models.CharField(max_length=20, blank=True, null=True)

    def description(self):
        return f"DOI: {self.doi}"

    def cite(self):
        txt = (
            f"{self.abbrev_authors()} ({self.date.year}). "
            f"<em>{self.title}</em>. <span class='text-body-secondary'>{self.journal.title} "
        )
        if self.volume:
            txt += self.volume
        if self.number:
            txt += f"({self.number}) "
        if self.pages:
            txt += f", {self.pages}"
        txt += '.</span>'
        if self.code:
            txt += f' <span class="text-body-secondary"><a target="blank" href="https://dx.doi.org/{self.code}">{self.code}</a>.</span>'
        if hasattr(self, 'pdbs') and self.pdbs.count():
            txt += ' [PDB: '
            txt += ', '.join([
                f'<a target="blank" href="https://www.rcsb.org/pdb/explore/explore.do?structureId={p.code}">{p.code}</a>'
                for p in self.pdbs.all()])
            txt += ']'
        return txt

    cite.short_description = 'Article'
    cite.allow_tags = True


class PDBDeposition(Publication):
    code = models.CharField(max_length=4, unique=True)
    reference = models.ForeignKey(Publication, related_name="pdbs", null=True, on_delete=models.SET_NULL)
    details = models.JSONField(default=dict)

    class Meta:
        verbose_name = 'Macromolecule Structure'

    def __str__(self):
        return f'{self.code}: {self.title}'

    def description(self):
        return f"PDB Code: {self.code}"

    def get_url(self):
        return 'https://www.rcsb.org/pdb/explore/explore.do?structureId={0}'.format(self.code)

    def cite(self):
        txt = f"{self.abbrev_authors()} ({self.date.year}). <em>{self.title}</em>. "
        txt += (
            f'Protein Data Bank: <span class="text-body-secondary">'
            f'<a target="blank" href="https://www.rcsb.org/pdb/explore/explore.do?structureId={self.code}">{self.code}</a>.'
            f'</span>'
        )

        return txt

    cite.short_description = 'PDB Entry'
    cite.allow_tags = True


def check_unique(title=None, authors=None, code=None):
    qf = None
    if title:
        qf = models.Q(title__icontains=title)
        if authors:
            qf &= models.Q(authors__icontains=authors)
    elif authors:
        qf = models.Q(authors__icontains=authors)
    if code:
        if not qf: qf = models.Q()
        qf |= models.Q(article__code__icontains=code)
        qf |= models.Q(book__code__icontains=code)
        qf |= models.Q(patent__code__icontains=code)
    matches = qf and Publication.objects.filter(qf) or Publication.objects.none()
    return matches.count() and matches.select_subclasses() or matches.none()
