

import datetime
import os
import random

import math
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy, reverse
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import DetailView, TemplateView, View
from django.views.generic.edit import FormView, UpdateView, CreateView

from . import forms
from . import models
from . import utils
from dynforms.views import DynCreateView
from misc.models import ActivityLog
from misc.views import JSONResponseMixin, ConfirmDetailView
from notifier import notify
from itemlist.views import ItemListView
from proxy.views import proxy_view
from publications import stats
from roleperms.views import RolePermsViewMixin


PROFILE_MANAGER = getattr(settings, 'PROFILE_MANAGER')
SITE_URL = getattr(settings, 'SITE_URL', '')


class UserDetailView(RolePermsViewMixin, DetailView):
    model = models.User
    slug_field = 'username'
    slug_url_kwarg = 'username'
    owner_fields = ['*', ]
    admin_roles = ['administrator:uso']
    template_name = "users/user_dashboard.html"

    def get_object(self, *args, **kwargs):
        # inject username in to kwargs if not already present
        if not self.kwargs.get('username'):
            self.kwargs['username'] = self.request.user.username
        self.kwargs['words'] = stats.get_keywords(self.request.user.publications.all(), transform=math.sqrt)
        return super().get_object(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['words'] = stats.get_keywords(self.request.user.publications.all(), transform=math.sqrt)
        if self.request.user.is_authenticated:
            context['admin'] = self.request.user.has_roles(self.admin_roles)
        else:
            context['admin'] = False
        return context


class TemplateDetailView(RolePermsViewMixin, TemplateView):
    template_name = "users/user_dashboard.html"


class SyncProfile(SuccessMessageMixin, RolePermsViewMixin, View):
    success_url = reverse_lazy('user-dashboard')
    success_message = "Profile synchronized"

    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            self.request.user.fetch_profile(force=True)
        return HttpResponseRedirect(self.success_url)


class InstitutionList(RolePermsViewMixin, ItemListView):
    template_name = "users/institution-list.html"
    model = models.Institution
    paginate_by = 25
    list_filters = ['modified', 'sector', 'state']
    list_columns = ['name', 'location', 'sector', 'state', 'num_users']
    list_search = ['name', 'location', 'sector', 'state', 'domains']
    ordering = ['-created']
    link_url = 'edit-institution'
    link_attr = 'data-url'
    link_field = 'name'
    list_styles = {'num_users': 'text-center', 'name': 'col-xs-4'}
    allowed_roles = ['administrator:uso', 'contracts-administrator']


class InstitutionDetail(JSONResponseMixin, DetailView):
    def get(self, request, *args, **kwargs):
        inst = None
        if 'name' in request.GET:
            inst = models.Institution.objects.filter(name__iexact=request.GET['name']).first()
        elif 'email' in request.GET:
            domains = ["@{}".format(email.split('@')[-1].lower().strip()) for email in request.GET['email'].split(',')]
            query = Q()
            for domain in domains:
                query |= Q(domains__icontains=domain)
            inst = models.Institution.objects.filter(query).first()

        if inst:
            address = [v.strip() for v in inst.location.split(',')]
            if len(address) == 3:
                city, province, country = address
            elif len(address) == 2:
                (city, country), province = address, ''
            elif len(address) == 1:
                city, province, country = '', '', address[0]
            else:
                city = province = country = ''
            context = {'institution': inst.name,
                       'sector': inst.sector,
                       'address.city': city,
                       'address.country': country,
                       'address.region': province,
                       }
        else:
            context = {}
        return self.render_to_response(context)


class InstitutionSearch(JSONResponseMixin, DetailView):
    def get(self, request, *args, **kwargs):
        found = models.Institution.objects.filter(name__icontains=request.GET['q']).order_by('name')
        if found.count():
            context = list(found.values_list('name', flat=True))
        else:
            context = []
        return self.render_to_response(context)


class InstitutionNames(JSONResponseMixin, View):
    def get(self, request, *args, **kwargs):
        context = list(models.Institution.objects.all().values_list('name', flat=True))
        return self.render_to_response(context)


class InstitutionEdit(RolePermsViewMixin, UpdateView):
    form_class = forms.InstitutionForm
    template_name = "forms/modal.html"
    model = models.Institution
    success_url = reverse_lazy('institution-list')
    success_message = "Institution '%(name)s' has been updated."
    allowed_roles = ['administrator:uso', 'contracts-administrator']

    def form_valid(self, form):
        super().form_valid(form)
        messages.success(self.request, "Institution '{}' has been updated.".format(self.object))
        return JsonResponse({'url': ""})


class InstitutionContact(RolePermsViewMixin, UpdateView):
    form_class = forms.InstitutionContactForm
    template_name = "forms/modal.html"
    queryset = models.Institution.objects.filter(state=models.Institution.STATES.new)
    allowed_roles = ['administrator:uso', 'user']

    def check_allowed(self):
        allowed = super().check_allowed()
        if not allowed and self.request.user.institution:
            allowed = self.request.user.institution.pk == self.kwargs['pk']
        return allowed

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(request=self.request)
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        data['state'] = models.Institution.STATES.pending
        data['modified'] = timezone.localtime(timezone.now())
        models.Institution.objects.filter(pk=self.object.pk).update(**data)
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.modify,
            description="Institution Contact Person information submitted"
        )
        return JsonResponse({'url': ""})


class UsersAdmin(RolePermsViewMixin, UpdateView):
    form_class = forms.UserAdminForm
    template_name = "users/forms/user-admin.html"
    model = models.User
    allowed_roles = ['administrator:uso']

    def get_initial(self):
        initial = super().get_initial()
        user = self.get_object()
        user.fetch_profile()
        initial['username'] = user.username
        initial['extra_roles'] = user.roles
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(request=self.request)
        return kwargs

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        obj.fetch_profile(force=True)
        return obj

    def form_valid(self, form):
        from proposals.models import Reviewer
        if form.has_changed():
            data = form.cleaned_data

            if 'reviewer' in data['extra_roles']:
                reviewer, created = Reviewer.objects.get_or_create(user=self.object)
                if created:
                    messages.info(self.request, "Reviewer Profile created")
            else:
                Reviewer.objects.filter(user=self.object).update(active=False)

            photo = data.pop('photo', None)

            if data or photo:
                profile = self.object.update_profile(data=data, photo=photo)
                if profile:
                    messages.info(self.request, "User Profile was updated.")
                else:
                    messages.error(self.request, "Unable to Update User profile in People Directory")
        else:
            messages.warning(self.request, "No Changes were applied!")
        return JsonResponse({'url': ""})


class InstitutionCreate(SuccessMessageMixin, RolePermsViewMixin, CreateView):
    form_class = forms.InstitutionForm
    template_name = "forms/modal.html"
    model = models.Institution
    success_url = reverse_lazy('institution-list')
    success_message = "Institution '%(name)s' has been created."
    allowed_roles = ['administrator:uso', 'contracts-administrator']


class InstitutionDelete(RolePermsViewMixin, UpdateView):
    model = models.Institution
    form_class = forms.InstitutionDeleteForm
    template_name = "forms/modal.html"
    success_url = reverse_lazy('institution-list')
    success_message = "Institution '%(name)s' has been deleted."
    allowed_roles = ['administrator:uso', 'contracts-administrator']

    def form_valid(self, form):
        data = form.cleaned_data
        if data['transfer']:
            data['transfer'].domains += self.object.domains
            self.object.users.all().update(institution=data['transfer'])
            data['transfer'].save()
        messages.success(self.request, "Institution '{}' has been deleted.".format(self.object.name))
        self.object.delete()
        return JsonResponse({'url': ""})


class UserList(RolePermsViewMixin, ItemListView):
    template_name = "item-list.html"
    model = models.User
    paginate_by = 25
    list_filters = ['modified', 'classification', 'institution']
    list_columns = ['get_full_name', 'email', 'username', 'address', 'institution']
    list_search = ['first_name', 'last_name', 'email', 'preferred_name']
    order_by = ['-created']
    link_url = 'users-admin'
    link_attr = "data-url"
    detail_target = "#modal-form"
    ordering_proxies = {'get_full_name': 'last_name'}
    allowed_roles = ['administrator:uso', 'contracts-administrator']


class RegistrationView(DynCreateView):
    template_name = "users/forms/registration_form.html"
    success_url = reverse_lazy("user-profile")
    form_class = forms.RegistrationForm
    model = models.Registration()

    def form_valid(self, form):
        reg = models.Registration.objects.create(**form.cleaned_data)
        recipients = [reg.details['contact']['email']]
        notify.send(recipients, "registration", context={
            'name': reg.details['names']['first_name'],
            'verification_url': f"{SITE_URL}{reverse_lazy('portal-verify', kwargs={'hash': reg.hash})}",
        })
        title = "Thank you!"
        msg = "You should receive an email shortly with instructions to complete the creation of your account."
        return render(self.request, 'users/forms/form_message.html', {'msg': msg, 'title': title})


API_ERRORS = {
    404: "We can't find the right place to do what you want! Start over, or contact the USO for assistance at "
         "clsuo@lightsource.ca or 306-657-3700.",
    403: "It looks like you're not allowed to do that. If the error persists, contact the USO for assistance at "
         "clsuo@lightsource.ca or 306-657-3700.",
    500: "There was an error completing your request. If the error persists, contact the USO for assistance at "
         "clsuo@lightsource.ca or 306-657-3700.",
}


class ResetPassword(FormView):
    template_name = "users/forms/reset.html"
    form_class = forms.PasswordResetForm

    def form_valid(self, form):
        data = form.cleaned_data
        user = models.User.objects.filter(
            email__iexact=data['email'], username__iexact=data['username'], last_name__iexact=data['last_name']
        ).first()
        if user:
            link = models.SecureLink(user=user)
            link.save()
            data = {
                'name': user.first_name,
                'reset_url': f"{SITE_URL}{reverse_lazy('password-reset', kwargs={'hash': link.hash})}",
            }
            recipients = [user.email]
            if user.alt_email:
                recipients.append(user.alt_email)
            notify.send(recipients, 'password-reset', context=data)

        # Security tip: do not give any feedback on whether user was found or not. Can't be used to find out who is
        # registered.
        return HttpResponseRedirect(reverse('user-dashboard'))


class PasswordView(UpdateView):
    valid_days = 1
    model = models.SecureLink
    form_class = forms.PasswordForm
    slug_url_kwarg = 'hash'

    def get_template_names(self):
        if self.object:
            return ["users/forms/password_form.html"]
        else:
            return ['users/forms/form_message.html']

    def get_object(self, *args, **kwargs):
        valid_date = timezone.now() - datetime.timedelta(days=self.valid_days)
        self.object = self.model.objects.filter(created__gte=valid_date).filter(hash__exact=self.kwargs['hash']).first()
        return self.object

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.object:
            context.update({
                'title': "Sorry!  It looks like there's a problem.",
                'msg': "Either the page you are looking for no longer exists or "
                       "you are attempting to re-use a single-use url."
            })
        else:
            context.update({
                'name': self.object.user.first_name,
                'title': 'Choose a new password',
            })
        return context

    def form_valid(self, form):
        info = {
            'username': self.object.user.username,
            'password': form.cleaned_data['password']
        }
        response = PROFILE_MANAGER.update_profile(info['username'], info)
        if response.status_code == 304:
            title = "Sorry!  Your password could not be changed."
            msg = 'Please try again with a different password or contact uso-support@lightsource.ca for assistance.'
        elif not response.ok:
            title = "Sorry!  It looks like there's a problem."
            if response.status_code in list(API_ERRORS.keys()):
                msg = API_ERRORS[response.status_code]
            else:
                msg = "There's something wrong with your request."
            if response.status_code == 400:
                try:
                    msg = msg + '<br><ul><li>' + '</li><li>'.join(
                        [f'{k}: {v[0]}' for k, v in response.json().items()]) + '</li></ul>'
                except:
                    pass
        else:
            title = "Success!"
            msg = (
                f"Your password has been changed.  A confirmation email containing your username "
                f"will be sent to you .Once you receive it, you can proceed "
                f"to <a href='{SITE_URL}{reverse_lazy('user-dashboard')}'>login</a>."
            )

            data = {
                'name': self.object.user.first_name,
                'username': self.object.user.username,
                'login_url': f"{SITE_URL}{reverse_lazy('user-dashboard')}",
            }
            recipients = [self.object.user.email]
            if self.object.user.alt_email:
                recipients.append(self.object.user.alt_email)
            notify.send(recipients, 'new-password', context=data)
            self.object.delete()
        return render(self.request, 'users/forms/form_message.html', {'msg': msg, 'title': title})


class VerifyView(PasswordView):
    model = models.Registration
    valid_days = 3

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.object:
            context.update({
                'title': "Sorry!  It looks like there's a problem.",
                'msg': "Either the page you are looking for no longer exists or "
                       "you are attempting to re-use a single-use url."
            })
        else:
            context['name'] = self.object.details['names']['first_name']
            context['title'] = 'Choose a password for your account'
            context[
                'description'] = 'After submitting the form, you will receive another email with your CLS Account Name.'
        return context

    def form_valid(self, form):
        from publications.models import SubjectArea
        from projects.models import Project
        from proposals.models import Submission
        details = self.object.details
        info = {
            'first_name': details['names']['first_name'],
            'last_name': details['names']['last_name'],
            'other_names': 'other_names' in details['names'] and details['names']['other_names'] or '',
            'email': details['contact']['email'],
            'password': form.cleaned_data['password'],
        }

        if details.get('student', '') == 'Yes':
            classification = details.get('category_1', '')
        else:
            classification = details.get('category_2', '')

        # Add student role or user role if already part of a project or proposal
        if classification == 'student':
            info['extra_roles'] = ['high-school-student']
        else:
            add_user_role = (
                    Submission.objects.filter(proposal__team__icontains=info['email']).exists() or
                    Project.objects.filter(team__email__iexact=info['email']).exists()
            )
            if add_user_role:
                info['extra_roles'] = ['user']

        # Add a message on the success page displaying the username?
        msg = title = ''
        if info:
            # Email the user with their new username
            title = "Congratulations!"
            msg = (f"You should receive an email containing your new CLS username. Once you've got it, go ahead "
                   f"and <a href='{reverse('user-dashboard')}'>login</a>!")

            research_field = SubjectArea.objects.filter(pk__in=details.get('research-field', []))
            initial = info
            initial.update({
                'classification': classification
            })

            address_info = {
                'address_1': details['department'],
                'address_2': details['address'].get('street', ''),
                'city': details['address'].get('city', ''),
                'region': details['address'].get('region', ''),
                'country': details['address'].get('country', ''),
                'postal_code': details['address'].get('code', ''),
                'phone': details['contact'].get('phone', ''),
            }
            i = models.Institution.objects.filter(name__iexact=details['institution']).first()
            if not i:
                location = ", ".join(
                    [_f for _f in [address_info['city'], address_info['region'], address_info['country']] if _f])
                i = models.Institution.objects.create(name=details['institution'], sector=details['sector'],
                                                      location=location)
            initial['institution'] = i
            initial['address'] = models.Address.objects.create(**address_info)

            # Call Profile Manager to add profile
            username = initial.pop('username')
            password = initial.pop('password')

            user = models.User.objects.create_user(username, password, **initial)
            user.research_field.add(*research_field)
            data = {
                'name': details['names']['first_name'],
                'username': user.username,
                'login_url': f"{SITE_URL}{reverse_lazy('portal-login')}",
            }
            recipients = [user.email]
            notify.send(recipients, "new-account", context=data)
            self.object.delete()

        return render(self.request, 'users/forms/form_message.html', {'msg': msg, 'title': title})


class UpdateUserProfile(RolePermsViewMixin, UpdateView):
    model = models.User
    form_class = forms.UserProfileForm
    template_name = "users/forms/profile.html"
    success_url = reverse_lazy("user-dashboard")
    allowed_roles = ['administrator:uso']

    def get_object(self, queryset=None):
        username = self.kwargs.get('username')
        if username:
            return models.User.objects.get(username=username)
        else:
            return self.request.user

    def check_allowed(self):
        allowed = super().check_allowed()
        if not allowed:
            user = self.get_object()
            allowed = (user == self.request.user)
        return allowed

    def get_initial(self, *args, **kwargs):
        initial = super().get_initial()
        user = self.get_object()
        #user.fetch_profile(force=True)
        if user.address:
            address_info = {
                k: getattr(user.address, k, '')
                for k in ['address_1', 'address_2', 'city', 'region', 'postal_code', 'phone', 'country']
                if getattr(user.address, k)
            }

            initial.update(address_info)
        if user.institution:
            initial['institution_name'] = user.institution.name
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        address_info = data.pop('address_info', {})
        institution_info = data.pop('institution_info', {})
        research_areas = data.pop('research_field')
        obj = self.get_object()
        old_institution = obj.institution
        if obj.address:
            models.Address.objects.filter(pk=obj.address.pk).update(**address_info)
        if institution_info:
            institution = models.Institution.objects.create(**institution_info)
            data['institution'] = institution
        else:
            institution = None
        if old_institution != institution:
            # FIXME: hard-coded name, perhaps the whole agreement thing needs to be re-thought
            obj.acceptances.filter(user=obj, agreement__name="CLSI User Agreement").update(active=False)
        models.User.objects.filter(username=obj.username).update(**data)

        info = {
            'title': obj.title,
            'first_name': obj.first_name,
            'last_name': obj.last_name,
            'other_names': obj.other_names,
            'email': obj.email.strip(),
        }
        # add student role if
        if obj.classification == 'student':
            info['extra_roles'] = set(obj.roles) | {'high-school-student'}

        # Call PeopleDirectory API "update_user"
        response = PROFILE_MANAGER.update_profile(obj.username, info)

        obj.research_field.set(research_areas)
        messages.success(self.request, "{}'s profile updated.".format(obj))
        return HttpResponseRedirect(self.success_url)


class ChangePassword(RolePermsViewMixin, View):
    def get(self, request, *args, **kwargs):
        user = request.user
        link = models.SecureLink.objects.create(user=user)
        data = {
            'name': user.first_name,
            'reset_url': f"{SITE_URL}{reverse_lazy('password-reset', kwargs={'hash': link.hash})}",
        }
        recipients = [user]
        if user.alt_email:
            recipients.append(user.alt_email)
        notify.send(recipients, 'password-reset', context=data)
        messages.success(
            self.request,
            ("A request to reset {}'s password has been received. "
             "Please check your email for further instructions.").format(user))

        return HttpResponseRedirect(reverse_lazy('user-dashboard'))


class PhotoView(View):
    def get(self, request, path=''):
        photo_url = settings.PROFILE_MANAGER.get_user_photo_url(path)
        return proxy_view(request, photo_url)


class EmailTestView(RolePermsViewMixin, View):
    allowed_roles = ["developer-admin"]

    def get(self, *args, **kwargs):
        from django.core.mail import mail_admins
        mail_admins("Email Test", "Testing email system!")
        messages.info(self.request, "Test Email has been sent, check your inbox.")
        url = reverse_lazy('user-dashboard')
        return HttpResponseRedirect(url)


class AdminResetPassword(RolePermsViewMixin, ConfirmDetailView):
    model = models.User
    template_name = "users/forms/admin-reset.html"
    allowed_roles = ['administrator:uso']

    def confirmed(self, *args, **kwargs):
        self.object = self.get_object()
        ActivityLog.objects.log(
            self.request, self.object, kind=ActivityLog.TYPES.modify,
            description='Users Password Reset'
        )
        utils.send_reset(self.object)
        return JsonResponse({"url": ""})
