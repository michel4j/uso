import hashlib
import json
import re
from datetime import timedelta

import phonenumbers
from crisp_modals.forms import ModalModelForm, Row, FullWidth, HalfWidth
from crispy_forms.bootstrap import PrependedText, AccordionGroup, Accordion, StrictButton, FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Div, Field, HTML
from django import forms
from django.db.models import Q
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.contrib.auth.forms import AuthenticationForm, UsernameField

from dynforms.forms import DynFormMixin
from misc.countries import COUNTRY_CODES
from publications.models import SubjectArea
from . import models
from . import utils
from .models import User, Institution, SecureLink, Registration

blank_choice = ((None, '------'),)


class InstitutionForm(forms.ModelForm):
    class Meta:
        model = Institution
        fields = ('name', 'location', 'sector', 'state', 'domains', 'parent', 'contact_person', 'contact_email', 'contact_phone')
        widgets = {
            "domains": forms.TextInput(),
        }
        help_texts = {
            'domains': 'Semi-colon separated list e.g.: @clsi.ca; @lightsource.ca',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()

        if kwargs.get('instance'):
            self.helper.title = "Edit Institution"
            self.helper.form_action = reverse_lazy('edit-institution', kwargs={'pk': self.instance.pk})
            btns = Div(
                Div(
                    HTML('<hr/>'), Div(
                        StrictButton(
                            'Delete', id="delete-object", css_class="btn btn-danger",
                            data_url=f"{reverse_lazy('delete-institution', kwargs={'pk': self.instance.pk})}"
                        ), css_class="text-left col-xs-6"
                    ), Div(
                        StrictButton('Revert', type='reset', value='Reset', css_class="btn btn-secondary"),
                        StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'), css_class='text-right col-xs-6'
                    ), css_class="row"
                )
            )
        else:
            self.helper.title = "Add Institution"
            self.helper.form_action = reverse_lazy('add-institution')
            btns = Div(
                Div(
                    HTML('<hr/>'), Div(
                        StrictButton('Revert', type='reset', value='Reset', css_class="btn btn-secondary"),
                        StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'), css_class='text-right col-xs-12'
                    ), css_class="row"
                )
            )

        self.helper.layout = Layout(
            Div(
                Div('name', css_class='col-sm-12'), Div(Field('location', placeholder='City, Region, Country'), css_class='col-sm-12'),
                Div(Field('sector', css_class="selectize"), css_class='col-sm-6'), Div(Field('state', css_class="selectize"), css_class='col-sm-6'),
                Div(Field('parent', css_class="selectize"), css_class='col-sm-12'), Div("domains", css_class='col-sm-12'),
                Div("contact_person", css_class='col-sm-12'), Div("contact_email", css_class='col-sm-6'), Div("contact_phone", css_class='col-sm-6'),
                css_class="row narrow-gutter"
            ), btns, )


class InstitutionContactForm(ModalModelForm):
    class Meta:
        model = Institution
        fields = ('contact_person', 'contact_email', 'contact_phone')

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)
        self.body.title = "Institutional Contact Person"
        self.body.form_action = self.request.get_full_path()
        self.body.append(
            Row(
                FullWidth(
                    HTML(
                        '<div class="alert alert-light">Please provide the contact details of the person at your '
                        'institution responsible to institutional agreements and contracts.</div>'
                    ),
                )
            ),
            Row(
                FullWidth("contact_person"),
                HalfWidth("contact_email"),
                HalfWidth("contact_phone"),
            )
        )


class InstitutionDeleteForm(ModalModelForm):
    transfer = forms.ModelChoiceField(
        label="Transfer Users To", required=False, queryset=models.Institution.objects.all()
    )

    class Meta:
        model = Institution
        fields = ('transfer',)
        help_texts = {
            'transfer': 'Transfer all users to this Institution before deleting',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()

        self.body.title = "Delete Institution?"
        self.body.form_action = reverse_lazy('delete-institution', kwargs={'pk': self.instance.pk})
        self.fields['transfer'].queryset = models.Institution.objects.exclude(pk=self.instance.pk)
        self.initial['transfer'] = self.instance.parent
        self.body.append(
            HTML(
                "<h5>Are you sure you want to delete the following Institution?</h5>"
                "<div class='minitron bg-danger text-danger'>"
                "<h4><strong>{{object}}</strong><br/>{{object.location}}</h4>"
                "<hr class='hr-xs'/>"
                "<small>Created {{object.created|date}}, &emsp;"
                "Last Modified {{object.modified|timesince}} ago</small>"
                "</div>"
            ),
            Div(Field('transfer', css_class="selectize"), css_class='col-sm-12'), css_class="row narrow-gutter"
        )


class PasswordResetForm(forms.Form):
    email = forms.EmailField(label="Email Address", required=True)
    last_name = forms.CharField(label="Last Name", required=True)
    username = forms.CharField(label="Username", required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "login-form-form"
        self.helper.layout = Layout(
            Div(
                Div(
                    Field('email'), css_class="col-xs-12"
                ), Div(
                    Field('last_name'), css_class="col-xs-6"
                ), Div(
                    Field('username'), css_class="col-xs-6"
                ), css_class="row"
            ), FormActions(
                Div(
                    Submit('submit', 'Request Reset', css_class='bg-primary col-xs-6 col-sm-4 pull-right'), css_class="col-xs-12"
                ), css_class="row"
            ), )


class RegistrationForm(DynFormMixin, forms.ModelForm):
    type_code = 'registration'

    class Meta:
        model = Registration
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_fields()

    def clean(self):
        cleaned_data = super().clean()

        email = cleaned_data['details'].get('contact', {}).get('email', '')
        country = cleaned_data['details'].get('address', {}).get('country', '')
        phone = cleaned_data['details'].get('contact', {}).get('phone', '')
        if not email:
            self._errors['contact'] = " Please enter a valid email address"

        elif User.objects.filter(Q(email__iexact=email) | Q(alt_email__iexact=email)).exists():
            self._errors['contact'] = " You already have an account in our system."

        code = COUNTRY_CODES.get(country.upper(), None)
        if phone and code:
            cleaned_phone = re.sub(r'\D', '', phone)
            try:
                phone_number = phonenumbers.parse(re.sub(r'\D', '', cleaned_phone), code)
                if code == 'CA':
                    phone = phonenumbers.format_number(phone_number, phonenumbers.PhoneNumberFormat.NATIONAL)
                else:
                    phone = phonenumbers.format_number(phone_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                cleaned_data['details']['contact']['phone'] = phone
            except:
                self._errors['contact'] = " Invalid Phone number for {}".format(country)

        oldreg = Registration.objects.filter(email__iexact=email).first()

        if oldreg and (timezone.now().today() - oldreg.created.replace(tzinfo=None)) < timedelta(days=3):
            raise forms.ValidationError(
                "Your previous registration is still pending. Check your email for instructions"
                " to complete your registration or wait 3 days for it to lapse."
            )
        elif oldreg:
            oldreg.delete()

        cleaned_data['email'] = email

        # create hash
        h = hashlib.new('ripemd160')
        h.update(email.encode('utf-8'))
        h.update(json.dumps(cleaned_data['details']).encode('utf-8'))
        h.update(timezone.now().isoformat().encode('utf-8'))
        cleaned_data['hash'] = h.hexdigest()
        return cleaned_data


class PasswordForm(forms.ModelForm):
    password = forms.CharField(label="", widget=forms.PasswordInput())
    confirm = forms.CharField(label="", widget=forms.PasswordInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.form_class = "login-form-form"
        self.helper.title = 'Choose a new password'
        self.helper.layout = Layout(
            Div(
                Div(
                    Field('password', placeholder="Password", css_class="form-control input-lg"), css_class="form-group left-inner-addon col-xs-12"
                ), Div(
                    Field('confirm', placeholder="Password again", css_class="form-control input-lg"),
                    css_class="form-group left-inner-addon col-xs-12"
                ), css_class="row"
            ), FormActions(
                Div(
                    Submit('submit', 'Submit', css_class='bg-primary col-xs-6 col-sm-4 pull-right'), css_class="col-xs-12"
                ), Div(
                    HTML('&nbsp;'), css_class="col-xs-12"
                ), css_class="row"
            ), )

    class Meta:
        fields = ('password', 'confirm')
        model = SecureLink

    def clean(self, *args, **kwargs):
        if 'password' in self.cleaned_data and 'confirm' in self.cleaned_data:
            _errors = []
            if self.cleaned_data['password'] != self.cleaned_data['confirm']:
                _errors.append("There was a typo in one of the entries.  Try again!")
            exp = r'^(?=.*[A-Z].*)(?=.*[a-z].*)(?=.*\d.*).{4,}'
            if not re.search(exp, self.cleaned_data['password']):
                _errors.append("Your password did not meet the requirements.  Try again!")
            if _errors:
                self._errors['password'] = _errors
        return super().clean(*args, **kwargs)


class PasswordChangeForm(forms.Form):
    old_password = forms.CharField(label="Current Password", widget=forms.PasswordInput())
    new_password = forms.CharField(label="New Password", widget=forms.PasswordInput())
    confirm = forms.CharField(label="Confirm New Password", widget=forms.PasswordInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.title = 'Change Password'
        self.helper.layout = Layout(

            Div(
                Div(
                    PrependedText(
                        'old_password', mark_safe("<i class='bi-shield-lock login-form-icon'></i>"), css_class="form-control"
                    ), css_class="form-group left-inner-addon col-xs-12"
                ), Div(
                    PrependedText(
                        'new_password', mark_safe("<i class='bi-shield-lock login-form-icon'></i>"), css_class="form-control"
                    ), css_class="form-group left-inner-addon col-xs-12"
                ), Div(
                    PrependedText(
                        'confirm', mark_safe("<i class='bi-shield-lock login-form-icon'></i>"), css_class="form-control"
                    ), css_class="form-group left-inner-addon col-xs-12"
                ), css_class="row"
            ), FormActions(
                Submit('form2', 'Change Password', css_class='button white')
            ),

        )


class UserAdminForm(ModalModelForm):
    extra_roles = forms.MultipleChoiceField(label='Additional Roles', required=False)

    class Meta:
        model = User
        fields = ['roles', 'photo']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)
        self.fields['extra_roles'].choices = utils.uso_role_choices()
        self.fields['extra_roles'].initial = self.instance.roles
        self.body.form_action = self.request.get_full_path()
        self.body.append(
            HTML("{% include 'users/user-admin.html' %}"),
            Row(
                HalfWidth(Field('extra_roles', css_class="selectize"),),
                HalfWidth(Field('photo', template='%s/file_field.html'))
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        extra_roles = cleaned_data.get('extra_roles', [])
        new_roles = [role for role in self.instance.roles if not role in utils.uso_role_choices()] + extra_roles
        cleaned_data['roles'] = new_roles
        return cleaned_data


class UserProfileForm(forms.ModelForm):
    institution_name = forms.CharField(label=_("Institution"), required=False)
    address_1 = forms.CharField(label="", max_length=255, required=True, help_text="Department")
    address_2 = forms.CharField(label="", max_length=255, required=False, help_text="Street Address")
    city = forms.CharField(label="", max_length=100, required=True, help_text="City")
    region = forms.CharField(label="", required=False, help_text="Province / State / Region")
    postal_code = forms.CharField(label="", max_length=100, required=False, help_text="Postal / Zip Code")
    country = forms.CharField(label="", required=False, help_text="Country")
    phone = forms.CharField(label="Phone Number", max_length=20, required=True)

    class Meta:
        model = User
        fields = [
            'research_field', 'classification', 'alt_email', 'title', 'first_name', 'last_name', 'preferred_name', 'email', 'emergency_contact',
            'emergency_phone', 'institution_name', 'address_1', 'address_2', 'city', 'region', 'postal_code', 'country', 'phone'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.title = "{}'s  Profile".format(self.instance)
        self.helper.layout = Layout(
            Fieldset(
                "Personal Information", Div(
                    Div(Field('title', css_class="selectize"), css_class='col-sm-2'), Div('first_name', css_class='col-sm-3'),
                    Div('last_name', css_class='col-sm-4'), Div('preferred_name', css_class='col-sm-3'), Div('email', css_class='col-sm-6'),
                    Div('alt_email', css_class='col-sm-6'), Div('phone', css_class='col-sm-6'), Div('emergency_phone', css_class='col-sm-6'),
                    css_class="row narrow-gutter"
                ), Div(
                    Div('emergency_contact', css_class='col-sm-12'), css_class="row narrow-gutter"
                ), Div(
                    Div(Field('research_field', css_class="selectize"), css_class='col-sm-12'), Div(
                        Field(
                            'institution_name', css_class='institution-input', placeholder="Type full name or select from existing entries"
                        ), css_class='col-sm-8'
                    ), Div(Field('classification', css_class="selectize"), css_class='col-sm-4'), css_class='row narrow-gutter'
                ), ), Fieldset(
                "Work Address", Div(
                    Div('address_1', css_class='col-sm-12'), Div('address_2', css_class='col-sm-12'), Div('city', css_class='col-sm-6'),
                    Div('country', placeholder="Type your country", css_class='col-sm-6'),
                    Div('region', placeholder="Type your province/state/territory", css_class='col-sm-6'), Div('postal_code', css_class='col-sm-6'),
                    css_class="address row narrow-gutter"
                ), ), FormActions(
                HTML('<hr class"hr-xs"/>'), Div(
                    StrictButton('Revert', type='reset', value='Reset', css_class="btn btn-secondary"),
                    StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'), css_class='text-right pull-right'
                ), ), )

    def clean(self):
        data = super().clean()
        # first_name/preferred_name/email
        first_name = data.get('first_name', '')
        preferred_name = data.get('preferred_name', '')
        if first_name and preferred_name and first_name.lower() == preferred_name.lower():
            data['preferred_name'] = None
        data['email'] = data['email'].lower().strip()

        # get address
        data['address_info'] = {
            k: data.pop(k, '') for k in ['address_1', 'address_2', 'city', 'region', 'postal_code', 'phone', 'country']
            if k in data
        }
        data['address_info']['modified'] = timezone.localtime(timezone.now())

        # get institution
        institution_name = data.pop('institution_name', '')
        if institution_name:
            institution = models.Institution.objects.filter(name__iexact=institution_name).first()
            data['institution'] = institution
            if not institution:
                data['institution_info'] = {
                    'name': institution_name, 'location': ", ".join(
                        [_f for _f in [data['address_info']['city'], data['address_info']['region'], data['address_info']['country']] if _f]
                    )
                }
        else:
            data['institution'] = None


class ProfileForm(forms.Form):
    title = forms.ChoiceField(
        label=_("Title"), choices=blank_choice + User.TITLES, required=False, )
    first_name = forms.CharField(
        label=_("First Name"), max_length=100, required=True, )
    last_name = forms.CharField(
        label=_("Last Name"), max_length=100, required=True, )
    other_names = forms.CharField(
        label=_("Other Names"), max_length=100, required=False, )
    email = forms.EmailField(
        label=_("Email Address"), required=True, )
    emergency_contact = forms.CharField(
        label=_("Emergency Contact's Full Name"), max_length=20, required=False, )
    emergency_phone = forms.CharField(
        label=_("Emergency Phone Number"), max_length=20, required=False, )
    research_field = forms.ModelMultipleChoiceField(
        label=_("Research Fields"), required=False, queryset=SubjectArea.objects.all(), )
    classification = forms.ChoiceField(
        label=_("Classification"), required=False, initial='', choices=blank_choice + User.CLASSIFICATIONS, )
    institution = forms.CharField(
        label=_("Institution"), required=False, )
    address_1 = forms.CharField(
        label="", max_length=255, required=True, help_text="Department", )
    address_2 = forms.CharField(
        label="", max_length=255, required=False, help_text="Street Address", )
    city = forms.CharField(
        label="", max_length=100, required=True, help_text="City", )
    region = forms.CharField(
        label="",  # choices=REGIONS,
        required=False, help_text="Province / State / Region", )
    postal_code = forms.CharField(
        label="", max_length=100, required=False, help_text="Postal / Zip Code", )
    country = forms.CharField(
        label="", required=False, help_text="Country", )
    phone = forms.CharField(
        label="Phone Number", max_length=20, required=True, )
    alt_email = forms.CharField(
        label="Alternate Email", max_length=20, required=False, )
    person_id = forms.IntegerField(
        widget=forms.HiddenInput, )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "style-form"
        self.helper.layout = Layout(
            Accordion(
                AccordionGroup(
                    _("Change Your Profile"), Div(
                        Div(Field('title', css_class="selectize"), css_class='col-sm-2'), Div('first_name', css_class='col-sm-3'),
                        Div('last_name', css_class='col-sm-4'), Div('other_names', css_class='col-sm-3'), Div('email', css_class='col-sm-6'),
                        Div('alt_email', css_class='col-sm-6'), Div('phone', css_class='col-sm-6'), Div('emergency_phone', css_class='col-sm-6'),
                        css_class="row narrow-gutter"
                    ), Div(
                        Div('emergency_contact', css_class='col-sm-12'), css_class="row narrow-gutter"
                    ), Div(
                        Div(Field('research_field', css_class="selectize"), css_class='col-sm-12'),
                        Div(Field('classification', css_class="selectize"), css_class='col-sm-6'), Div(
                            Field(
                                'institution', css_class='institution-input', placeholder="Type full name or select from existing entries"
                            ), css_class='col-sm-6'
                        ), css_class='row narrow-gutter'
                    ), Fieldset(
                        "Work Address", Div(
                            Div('address_1', css_class='col-sm-12'), Div('address_2', css_class='col-sm-12'),
                            Div('country', placeholder="Type your country", css_class='col-sm-6'), Div(
                                'region', placeholder="Type your province/state/territory", css_class='col-sm-6'
                            ), Div('city', css_class='col-sm-6'), Div('postal_code', css_class='col-sm-6'), css_class="address row narrow-gutter"
                        ), ), FormActions(
                        Submit('form', 'Save', css_class='button white')
                    ), active=True
                ), ), 'person_id'
        )


class LoginForm(AuthenticationForm):
    username = UsernameField(
        label=_("Username"),     widget=forms.TextInput(attrs={'autofocus': True}),
    )
    password = forms.CharField(
        label=_("Password"), strip=False, widget=forms.PasswordInput,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "login-form"
        self.helper.layout = Layout(
            Div(
                Div(
                    Field('username', placeholder="Username", css_class="form-control input-md"),
                    css_class="form-group left-inner-addon col-xs-12"
                ), Div(
                    Field('password', placeholder="Password", css_class="form-control input-md"),
                    css_class="form-group left-inner-addon col-xs-12"
                ),
                css_class="row"
            ), FormActions(
                Div(
                    Submit('submit', 'Login', css_class='bg-primary'),
                    css_class="col-xs-12"
                ),
                css_class="row"
            )
        )

