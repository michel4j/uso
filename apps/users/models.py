import functools
import hashlib
import json
import operator
import os
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q, ForeignKey
from django.dispatch.dispatcher import receiver
from django.utils import timezone
from django.utils.translation import gettext as _
from dynforms.models import BaseFormModel
from model_utils import Choices
from model_utils.models import TimeStampedModel

from misc.fields import StringListField
from misc.models import DateSpanMixin
from roleperms.models import RolePermsUserMixin

USO_ADMIN_ROLES = getattr(settings, 'USO_ADMIN_ROLES', [''])
USO_STAFF_ROLES = getattr(settings, 'USO_STAFF_ROLES', [''])
USO_REVIEWER_ROLES = getattr(settings, 'USO_REVIEWER_ROLES', ['reviewer'])
USO_PROFILE_MANAGER = getattr(settings, 'USO_PROFILE_MANAGER')


class CountryManager(models.Manager):
    def get_by_natural_key(self, code):
        return self.get(alpha3=code)


class Country(models.Model):
    """
    Model to store country data based on ISO 3166-1 standard.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="The common name of the country."
    )
    alpha2 = models.CharField(
        max_length=2,
        unique=True,
        verbose_name="ISO 3166-1 alpha-2",
        help_text="Two-letter country code."
    )
    alpha3 = models.CharField(
        max_length=3,
        unique=True,
        verbose_name="ISO 3166-1 alpha-3",
        help_text="Three-letter country code."
    )
    code = models.CharField(
        max_length=3,
        unique=True,
        blank=True,
        null=True,
        verbose_name="ISO 3166-1 numeric code",
        help_text="Three-digit country code."
    )

    objects = CountryManager()

    class Meta:
        verbose_name_plural = "Countries"
        ordering = ['name']

    def natural_key(self):
        return (self.alpha3,)

    def __str__(self):
        return self.name


class RegionManager(models.Manager):
    def get_by_natural_key(self, code):
        return self.get(code=code)


class Region(models.Model):
    """
    Model for top-level administrative subdivisions of a country (e.g., state, province).
    Corresponds to ISO 3166-2.
    """
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="regions")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10,  unique=True,  verbose_name="ISO 3166-2 code")
    lat = models.FloatField(null=True, blank=True, verbose_name="Latitude")
    lon = models.FloatField(null=True, blank=True, verbose_name="Longitude")
    objects = RegionManager()

    class Meta:
        verbose_name_plural = "Regions"
        unique_together = [['country', 'name']]
        ordering = ['country__name', 'name']

    def natural_key(self):
        return (self.code,)

    def __str__(self):
        return f"{self.name}, {self.country.name}"


class Address(TimeStampedModel):
    address_1 = models.CharField(_('Department'), max_length=255)
    address_2 = models.CharField(_('Street'), max_length=255, blank=True)
    address_3 = models.CharField(_('Place'), max_length=255, blank=True)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(_('Postal/Zip Code'), max_length=100, blank=True)
    region = ForeignKey(Region, null=True, blank=True, on_delete=models.SET_NULL)
    country = ForeignKey(Country, null=True, blank=True, on_delete=models.SET_NULL)
    phone = models.CharField(_('Phone Number'), max_length=20, blank=True)

    class Meta:
        verbose_name_plural = _("Addresses")

    def __str__(self):
        place = ", ".join([a for a in [self.address_1, self.address_2, self.address_3] if a.replace('-', '').strip()])
        return f"{place}, {self.city}, {self.region}"

    def api_format(self):
        address_2 = self.address_2 and f'{"+".join(self.address_2.split())},+' or ''
        address_3 = ''
        region = self.region and f'{"+".join(self.region.split())},+' or ''
        postal_code = self.postal_code and f'{"+".join(self.postal_code.split())},+' or ''
        return f"{address_2}{address_3}{'+'.join(self.city.split())},+{region}{postal_code}{'+'.join(self.country.split())}"


class CustomUserManager(BaseUserManager):
    def get_by_natural_key(self, username):
        return self.get(username=username)

    def create_user(self, username, password=None, **other_fields):
        """
        Creates and saves a Person with the given details.
        """
        missing_fields = list(set(self.model.REQUIRED_FIELDS) - set(other_fields.keys()))
        if len(missing_fields) > 0:
            raise ValueError(f'Users must have  {", ".join(missing_fields)}')

        other_fields['username'] = username
        user = self.model(**other_fields)
        user.set_password(password)
        user.save(using=self._db)
        USO_PROFILE_MANAGER.create_profile(other_fields)
        return user

    def create_local_user(self, username):
        profile = USO_PROFILE_MANAGER.fetch_profile(username)
        if profile:
            user = self.create_user(username)
            user.fetch_profile(force=True)
        else:
            user = None
        return user

    def create_superuser(self, username, password, **other_fields):
        """
        Creates and saves a superuser with the given username and password.
        """
        other_fields['roles'] = USO_ADMIN_ROLES
        if os.environ.get('DJANGO_SUPERUSER_EMAIL'):
            other_fields['email'] = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        if os.environ.get('DJANGO_SUPERUSER_FIRST_NAME'):
            other_fields['first_name'] = os.environ.get('DJANGO_SUPERUSER_FIRST_NAME')
        if os.environ.get('DJANGO_SUPERUSER_LAST_NAME'):
            other_fields['last_name'] = os.environ.get('DJANGO_SUPERUSER_LAST_NAME')
        user = self.create_user(username, password=password, **other_fields)
        return user

    def all_with_roles(self, *roles: str):
        expr = functools.reduce(operator.__or__, [Q(roles__iregex=f'<{role}(:.+)?>') for role in roles], Q())
        return self.filter(expr)

    def all_with_permissions(self, *perms: str):
        expr = functools.reduce(operator.__and__, [Q(permissions__icontains=f'<{perm}>') for perm in perms], Q())
        return self.filter(expr)


def name_initials(name: str) -> str:
    """
    :type name: str
    :param name: string
    :return:
    """
    name = '' if not name else name.strip()
    return '' if not name else name[0].upper() + '. '


class User(AbstractBaseUser, TimeStampedModel, RolePermsUserMixin):
    STUDENTS = Choices(
        ('student', _('K-12 Student')),
        ('undergraduate', _('Undergraduate Student')),
        ('masters', _('Masters Student')),
        ('doctorate', _('Doctorate Student')),
        ('postdoc', _('Post Doctorate')),
    )
    STAFF = Choices(
        ('faculty', _('Faculty')),
        ('professional', _('Professional')),
        ('other', _('Other')),
    )
    CLASSIFICATIONS = STUDENTS + STAFF
    TITLES = Choices(
        ('Prof', _('Prof')),
        ('Mr', _('Mr')),
        ('Ms', _('Ms')),
        ('Dr', _('Dr')),
        ('Sr', _('Sir')),
    )

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    username = models.SlugField(unique=True)
    institution = models.ForeignKey(
        'Institution', null=True, blank=True, related_name='users',
        on_delete=models.PROTECT
    )
    address = models.OneToOneField(Address, null=True, blank=True, on_delete=models.SET_NULL)
    research_field = models.ManyToManyField("publications.SubjectArea", blank=True)
    classification = models.CharField(choices=CLASSIFICATIONS, null=True, blank=True, max_length=20)
    alt_email = models.EmailField(_("Alternate Email"), null=True, blank=True)
    objects = CustomUserManager()

    # The following fields are only updated by the update_profile method which fetches current
    # information from the People DB.
    title = models.CharField(choices=TITLES, max_length=20, null=True, blank=True)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    preferred_name = models.CharField(_("Preferred First Name"), max_length=100, null=True, blank=True)
    other_names = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(unique=True, default=uuid.uuid4)
    photo = models.URLField(null=True, blank=True)
    emergency_contact = models.CharField(_("Emergency Contact (Full Name)"), max_length=100, null=True, blank=True)
    emergency_phone = models.CharField(max_length=20, null=True, blank=True)
    roles = StringListField(blank=True)
    permissions = StringListField(blank=True)
    last_updated = models.DateTimeField(null=True, blank=True)

    @property
    def is_staff(self):
        return self.has_any_role(*USO_ADMIN_ROLES)

    @property
    def is_superuser(self):
        return self.has_any_role(*USO_ADMIN_ROLES)

    def can_review(self):
        return (
                self.classification in [self.STAFF.faculty, self.STAFF.professional]
        ) and not self.has_any_role(*USO_STAFF_ROLES)

    def is_reviewer(self):
        return hasattr(self, 'reviewer')

    def fetch_profile(self, force=False, delay=15):
        # update profile only once per `delay` minutes
        if not self.last_updated:
            force = True
        now = timezone.localtime(timezone.now())

        # update the data
        if force or self.last_updated <= now - timedelta(minutes=delay):
            profile = USO_PROFILE_MANAGER.fetch_profile(self.username)
            for key, val in profile.items():
                if key in USO_PROFILE_MANAGER.PROFILE_FIELDS:
                    setattr(self, key, val)

            self.last_updated = now
            self.save()

    def update_profile(self, data=None, photo=None):
        # update remote profile in PeopleDB
        data = {} if not data else data
        if data or photo:
            profile = USO_PROFILE_MANAGER.update_profile(self.username, data, photo=photo)
            if profile:
                self.fetch_profile()
                return profile
        return data

    def __str__(self):
        return self.get_full_name()

    def get_photo(self):
        return USO_PROFILE_MANAGER.get_user_photo_url(self.username)

    def initials(self):
        return ''.join(
            [n[0] for n in [self.preferred_name or self.first_name, self.other_names, self.last_name] if n]
        ).upper()

    def get_full_name(self):
        first_name = (self.first_name or self.preferred_name)
        last = '' if not self.last_name else f'{self.last_name}'
        first = '' if not first_name else f'{first_name} '
        return f'{first} {last}'

    def get_name_variants(self):
        first_initials = name_initials(self.first_name)
        other_initials = name_initials(self.other_names)
        last_first = '' if not self.last_name else f'{self.last_name},'
        first_first = '' if not self.first_name else f'{self.first_name} '
        last_last = '' if not self.last_name else f'{self.last_name}'

        return [
            f'{last_first}{first_initials}{other_initials}'.strip(),
            f'{last_first}{first_initials}'.strip(),
            f'{last_first}{other_initials}'.strip(),
            f'{first_first}{other_initials}{last_last}'.strip(),
            f'{first_first}{last_last}'.strip(),
            self.get_full_name(),
        ]

    def get_short_name(self):
        return self.preferred_name if self.preferred_name else self.first_name

    def get_all_permissions(self):
        return set(self.permissions)

    def get_all_roles(self):
        return {r.lower().strip() for r in self.roles}

    get_full_name.short_description = "Full Name"
    get_full_name.sort_field = 'first_name'


class Institution(DateSpanMixin, TimeStampedModel):
    SECTORS = Choices(
        ('k12', _('K-12 Academic')),
        ('academic', _('Post-Secondary Academic')),
        ('research', _('Research')),
        ('synchrotron', _('Synchrotron')),
        ('government', _('Government')),
        ('industry', _('Industry')),
    )
    STATES = Choices(
        ('new', _('New')),
        ('pending', _('Pending')),
        ('started', _('Started')),
        ('active', _('Active')),
        ('exempt', _('Exempt')),
        ('expired', _('Expired')),
    )
    name = models.CharField(max_length=200, unique=True)
    country = models.ForeignKey(Country, null=True, blank=True, on_delete=models.SET_NULL)
    region = models.ForeignKey(Region, null=True, blank=True, on_delete=models.SET_NULL)
    city = models.CharField(max_length=200, null=True, blank=True)
    sector = models.CharField(null=True, blank=True, max_length=20, choices=SECTORS)
    domains = StringListField(_("Institutional Email Suffixes"), blank=True, null=True)
    state = models.CharField("Agreement", max_length=20, choices=STATES, default=STATES.new)
    parent = models.ForeignKey(
        "Institution", null=True, blank=True, verbose_name=_('Parent Institution'), on_delete=models.SET_NULL
    )
    contact_person = models.CharField("Contact Person", max_length=200, blank=True)
    contact_email = models.EmailField("Contact Email", blank=True)
    contact_phone = models.CharField("Contact Phone", max_length=50, blank=True)

    def num_users(self):
        return self.users.count()

    num_users.short_description = 'Users'
    num_users.sort_field = 'users__id'

    @property
    def location(self):
        return f"{self.city}, {self.region}"

    def email_users(self):
        if self.domains:
            query = models.Q()
            for domain in self.domains:
                query |= models.Q(email__iendswith=domain) | models.Q(alt_email__iendswith=domain)
            return User.objects.filter(query)
        else:
            return User.objects.none()

    def __str__(self):
        return self.name


class Registration(BaseFormModel):
    hash = models.CharField(max_length=50, unique=True)
    email = models.CharField(max_length=250)

    def __str__(self):
        return f"{self.email} - {self.hash}"

    def text(self):
        info = {
            'first_name': self.details['names']['first_name'],
            'last_name': self.details['names']['last_name'],
            'other_names': 'other_names' in self.details['names'] and self.details['names']['other_names'] or '',
            'email': self.details['contact']['email'],
        }
        if self.details.get('student', '') == 'Yes':
            info['classification'] = self.details.get('category_1', '')
        else:
            info['classification'] = self.details.get('category_2', '')
        info['address'] = {
            'address_1': self.details['department'],
            'address_2': self.details['address'].get('street', ''),
            'city': self.details['address'].get('city', ''),
            'region': self.details['address'].get('region', ''),
            'country': self.details['address'].get('country', ''),
            'postal_code': self.details['address'].get('code', ''),
            'phone': self.details['contact'].get('phone', ''),
        }
        return json.dumps(info, indent=4)


class SecureLink(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    hash = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return f'{self.user} - [{timezone.localtime(self.created).strftime("%Y%m%d %X")}] {self.hash}'


@receiver(models.signals.pre_save, sender=SecureLink)
def on_secure_link_save(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    if instance.pk is None:
        h = hashlib.new('ripemd160')
        h.update(f'{str(instance.user)}-{instance.created}'.encode('utf-8'))
        instance.hash = h.hexdigest()
