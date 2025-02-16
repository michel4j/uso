
from datetime import timedelta, date, time, datetime

from crispy_forms.bootstrap import StrictButton, PrependedText, AppendedText, InlineCheckboxes, InlineRadios
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, HTML
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q, TextChoices
from django.utils import timezone
from django.utils.safestring import mark_safe

from . import models
from beamlines.models import FacilityTag, Lab, LabWorkSpace
from dynforms.forms import DynFormMixin
from misc.utils import Joiner
from proposals.models import ReviewCycle
from scheduler.utils import round_time


class DateField(AppendedText):
    def __init__(self, field_name, *args, **kwargs):
        super().__init__(field_name, mark_safe('<i class="bi-calendar"></i>'), *args, **kwargs)


class ProjectForm(DynFormMixin, forms.ModelForm):
    type_code = 'project'

    class Meta:
        model = models.Project
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_fields()

    def clean(self):
        User = get_user_model()
        data = super().clean()
        data['title'] = data['details'].get('title')
        if not data['title']:
            self._errors['title'] = "You must add a title before you can save the project "
        data['cycle'] = ReviewCycle.objects.filter(pk=data['details'].get('first_cycle')).last()
        return data


class MaterialForm(DynFormMixin, forms.Form):
    type_code = 'amendment'

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)
        self.init_fields()


class ExtensionForm(forms.ModelForm):
    shifts = forms.IntegerField(label="Additional Number of Shifts", required=True)

    class Meta:
        model = models.Session
        fields = ["shifts"]
        widgets = {
            'shifts': forms.NumberInput(attrs={'min': 1, 'max': 10}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        self.session = kwargs.pop('session', None)
        super().__init__(*args, **kwargs)

        self.fields['shifts'].initial = 1
        self.helper = FormHelper()
        self.helper.title = "Extend Session"
        self.helper.form_action = self.request.path
        self.helper.layout = Layout(
            Div(
                Div(
                    HTML(
                        "<div class='alert alert-info'>"
                        "<strong>{{session.project}}</strong>: {{session.start}} &mdash; {{session.end}}"
                        "</div>"
                    ),
                ),
                Field("shifts", css_class="col-sm-12"),
                css_class="row modal-body"
            ),
            Div(css_class="modal-body"),
            Div(
                Div(
                    StrictButton('Cancel', type='button', data_dismiss='modal', css_class="btn btn-default pull-left"),
                    StrictButton('Extend', type='submit', value='Save', css_class='btn btn-primary pull-right'),
                    css_class="col-xs-12"
                ),
                css_class="row modal-footer"
            )
        )


def shift_choices(name="Shifts", size=8, show_now=False):
    times = list(range(0, 24, size))
    choices = {}

    if show_now:
        now = timezone.localtime(timezone.now())
        choices["NOW"] = (now.strftime('%H:%M'), now.strftime('Now %H:%M'))
    for h in times:
        choices[f"T{h:02d}"] = (f'{h:02d}:00', f'{h:02d}:00')

    return TextChoices(name, choices)


class HandOverForm(forms.ModelForm):
    start_date = forms.DateField(required=True)
    end_date = forms.DateField(required=True)
    start_time = forms.ChoiceField(required=True, choices=shift_choices(show_now=False))
    end_time = forms.ChoiceField(required=True, choices=shift_choices(show_now=False))

    class Meta:
        model = models.Session
        fields = ['start', 'end', 'kind', 'start_time', 'end_time', 'start_date', 'end_date']
        widgets = {
            'start': forms.HiddenInput,
            'end': forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        self.project = kwargs.pop('project', None)
        self.facility = kwargs.pop('facility', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.title = "Hand-over Beamtime"
        self.helper.form_action = self.request.path
        self.fields['kind'].help_text = (
            "<em>On-Site:</em>  Users will be physically present at the facility, <br/>"
            "<em>Remote:</em>  Users will perform the experiments by connecting through the internet,<br/>"
            "<em>Mail-In:</em> Staff will be performing the experiment on behalf of the users."
        )

        # adjust widget shift size based on beamline
        start_choices = shift_choices("ShiftsNow", size=self.facility.shift_size, show_now=True)
        end_choices = shift_choices("Shifts", size=self.facility.shift_size)

        self.fields['start_time'].choices = start_choices.choices
        self.fields['start_time'].initial = start_choices.NOW
        self.fields['end_time'].choices = end_choices.choices

        self.helper.layout = Layout(
            Div(
                HTML(
                    "<div class='tinytron'>\n"
                    "    <h4 class='overflow ellipsis'>Project: {{project}}&mdash;<strong class='text-condensed'>{{project.title}}</strong></h4>\n"
                    "    <h4>Facility: {{facility.acronym}}&mdash;<strong class='text-condensed'>{{facility.name}}</strong></h4>\n"
                    "	{% if tags %}\n"
                    "	<div class=\"row\">\n"
                    "		<div class='col-sm-12 text-right' style='line-height: 1.6;'>\n"
                    "		{% for tag in facility.tags.all %}\n"
                    "			{% if tag in tags %}\n"
                    "			<span id='tag-{{tag.pk}}' class='label bg-cat-{{forloop.counter}}'>{{tag}}</span>\n"
                    "			{% endif %}\n"
                    "		{% endfor %}\n"
                    "		</div>\n"
                    "	</div>\n"
                    "	{% endif %}\n"
                    "</div>\n"
                ),
                css_class="row modal-body"
            ),
            Div(
                Div(DateField('start_date'), css_class='col-sm-6'),
                Div(DateField('end_date'), css_class='col-sm-6'),
                Div(Field('start_time', css_class="chosen"), css_class='col-sm-6'),
                Div(Field('end_time', css_class="chosen"), css_class='col-sm-6'),
                Div(Field("kind", css_class="chosen"), css_class="col-xs-12"),
                css_class="row"
            ),
            Div(
                Div(
                    StrictButton('Cancel', type='button', data_dismiss='modal', css_class="btn btn-default pull-left"),
                    StrictButton('Hand-Over', type='submit', value='Save', css_class='btn btn-primary pull-right'),
                    css_class="col-xs-12"
                ),
                css_class="row modal-footer"
            )
        )

    def clean(self):
        cleaned_data = super().clean()

        for field in ['start_date', 'end_date', 'start_time', 'end_time']:
            if not (field in cleaned_data and cleaned_data.get(field)):
                continue

            elif field in ['start_time', 'end_time']:
                cleaned_data[field] = datetime.strptime(cleaned_data[field], '%H:%M').time()

        for name in ['start', 'end']:
            if f'{name}_date' in cleaned_data and f'{name}_time' in cleaned_data:
                cleaned_data[name] = timezone.make_aware(
                    datetime.combine(cleaned_data[f'{name}_date'], cleaned_data[f'{name}_time'])
                )

        if cleaned_data['start'] and cleaned_data['end']:
            if self.project.start_date > cleaned_data['start'].date():
                self.add_error(None, 'Session must start while project is active')
            if self.project.end_date and (self.project.end_date < cleaned_data['end'].date()):
                self.add_error(None, 'Session must end before project expires')
            if cleaned_data['end'] <= cleaned_data['start']:
                self.add_error(None, 'Session must end later than its starting time')

        for field in ['start_date', 'end_date', 'start_time', 'end_time']:
            if field in cleaned_data:
                del cleaned_data[field]
        return cleaned_data


class LabSessionForm(forms.ModelForm):
    class Meta:
        model = models.LabSession
        fields = ['lab', 'workspaces', 'equipment', 'start', 'end', 'team']
        widgets = {
            'team': forms.CheckboxSelectMultiple,
            'workspaces': forms.CheckboxSelectMultiple,
            'start': forms.DateTimeInput,
            'end': forms.DateTimeInput,
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        self.project = kwargs.pop('project')
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.title = "Lab Sign-On"
        self.helper.form_action = self.request.path
        self.fields['team'].queryset = self.project.team.filter()
        self.fields['team'].help_text = (
            "Select all team members who will be using the lab during this session. "
            "Only team members who have the appropriate qualifications to use the lab can be added."
        )
        self.fields['lab'].help_text = (
            "See <a href='http://www.lightsource.ca/pages/wet_lab_equipment.html' "
            "target='_blank'>additional information</a>."
        )
        self.fields['lab'].queryset = Lab.objects.filter(available=True)
        self.fields['workspaces'].queryset = LabWorkSpace.objects.filter(available=True)
        self.fields['workspaces'].help_text = (
            "Select the workspaces you will be using in the lab during this session. If the workstation is already"
            "booked for the selected period, you will be prompted to select another one."
        )
        self.fields['equipment'].help_text = (
            "Please select all ancillary equipment you plan to use in the lab during this session"
        )

        for field in ['start', 'end', 'team']:
            self.fields[field].required = True

        self.fields['team'].required = True

        self.helper.layout = Layout(
            Div(
                HTML(
                    "<div class='tinytron'>\n"
                    "    <h4 class='overflow ellipsis'>Project: {{project}}&mdash;<strong class='text-condensed'>{{project.title}}</strong></h4>\n"
                    "</div>\n"
                ),
                css_class="row modal-body"
            ),
            Div(
                Div(Field("lab", css_class="chosen"), css_class="col-sm-5"),
                Div(
                    Div(
                        Div('start', css_class='col-sm-6'),
                        Div('end', css_class='col-sm-6'),
                        css_class="row narrow-gutter"
                    ),
                    css_class="col-sm-7"
                ),
                Div(Field("equipment", css_class="chosen"), css_class="col-sm-12"),
                css_class="row narrow-gutter"
            ),
            Div(
                Div(InlineCheckboxes("workspaces"), css_class="col-xs-12"),
                css_class="row"
            ),
            Div(
                Div(InlineCheckboxes("team"), css_class="col-xs-12"),
                css_class="row"
            ),
            Div(
                Div(
                    StrictButton('Cancel', type='button', data_dismiss='modal', css_class="btn btn-default pull-left"),
                    StrictButton('Sign-On', type='submit', value='Save', css_class='btn btn-primary pull-right'),
                    css_class="col-xs-12"
                ),
                css_class="row modal-footer"
            )
        )

    def clean(self):
        from agreements.models import Agreement
        cleaned_data = super().clean()
        user_agreement = Agreement.objects.get(
            code="80ae507a-d622-4792-b376-f9f5b4b02ae0"
        )  # FIXME, hard coded, better design needed
        failures = []

        lab = cleaned_data.get('lab')
        team = cleaned_data.get('team')
        equipment = cleaned_data.get('equipment')
        start = cleaned_data.get('start')
        end = cleaned_data.get('end')
        workspaces = cleaned_data.get('workspaces')
        joiner = Joiner(', ', ' & ')

        if lab and team:
            lab_permissions = [_f for _f in lab.permissions.values_list('code', flat=True) if _f]
            unqualified = [
                member
                for member in team
                if not member.has_all_perms(*lab_permissions)
            ]
            if unqualified:
                msg = (
                    "Use of the {} requires {} permissions for all participating team members. The following "
                    "selected team members did not qualify: {}.".format(
                        lab, joiner(lab_permissions), joiner(unqualified)
                    )
                )
                self.add_error('team', 'Unqualified users selected.')
                failures.append(msg)

        if team and equipment:
            missing_agreements = [
                member
                for member in team
                if not user_agreement.valid_for_user(member)
            ]
            if missing_agreements:
                msg = (
                    "All participating team members must have valid User Agreements. "
                    "The following users do not: {}.".format(
                        joiner(missing_agreements)
                    )
                )
                self.add_error('team', 'Unqualified users selected.')
                failures.append(msg)

            equipment_perms = [_f for _f in equipment.values_list('permissions__code', flat=True) if _f]
            if equipment_perms:
                unqualified = [
                    member
                    for member in team
                    if not member.has_all_perms(*equipment_perms)
                ]
                if unqualified:
                    msg = (
                        "Use of the selected equipment requires {} permissions for all participating team members. "
                        "The following selected team members did not qualify: {}.".format(
                            lab, joiner(equipment_perms), joiner(unqualified)
                        )
                    )
                    self.add_error('equipment', 'Required permissions missing.')
                    failures.append(msg)

        if start and end:
            if self.project.end_date and self.project.end_date < end.date():
                msg = 'Project expires on {}!'.format(
                    self.project.end_date.isoformat()
                )
                self.add_error('end', msg)

            if start > end:
                self.add_error('end', "End earlier than Start!")

            if workspaces and start and end:
                conflicts = models.LabSession.objects.filter(lab=lab, workspaces__in=workspaces).intersects(
                    cleaned_data
                ).distinct()
                if self.instance:
                    conflicts = conflicts.exclude(pk=self.instance.pk)
                if conflicts.exists():
                    self.add_error('workspaces', "Booking conflicts")
                    self.add_error('start', "Booking conflicts")
                    self.add_error('end', "Booking conflicts")
                    msg = "The following conflicts have been identified in the {}:".format(lab)
                    msg += "<ul>"
                    for conflict in conflicts:
                        msg += "<li>{} busy from {} &mdash; {}. </li>".format(
                            joiner(conflict.workspaces.all()),
                            conflict.start.strftime('%c'), conflict.end.strftime('%c')
                        )
                    msg += "</ul>"
                    failures.append(msg)
        if failures:
            raise forms.ValidationError(mark_safe('<br/>'.join(failures)), code='invalid')

        return cleaned_data


class SessionForm(forms.ModelForm):
    class Meta:
        model = models.Session
        fields = ['samples', 'team', 'staff']
        widgets = {
            'samples': forms.CheckboxSelectMultiple,
            'team': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        self.session = self.instance
        self.material = self.session.project.materials.approved().last()

        query = Q(state='approved') & (Q(expiry__isnull=True) | Q(expiry__gte=self.session.end))

        if self.material:
            self.fields['samples'].queryset = self.material.project_samples.filter(query).distinct()
            self.fields['samples'].help_text = (
                "Select all samples that will be on-site during this session. "
                "Only samples present on-site should be selected. Only approved samples can be selected"
            )
        else:
            self.fields['samples'].queryset = models.Material.objects.none()
            self.fields['samples'].help_text = (
                "Select all samples that will be on-site during this session. "
                "Only samples present on-site should be selected. Only approved samples can be selected"
            )

        self.fields['team'].queryset = self.session.project.team.all()
        self.fields['team'].help_text = (
            "Select all team members who will be participating during this session. "
            "Only team members who have the appropriate permissions can be added."
        )
        self.fields['staff'].queryset = self.session.beamline.staff_list()
        self.fields['staff'].help_text = (
            "Select the staff member who will be present during this session. "
        )
        self.helper = FormHelper()
        self.helper.title = "Beamtime Sign-On"
        self.helper.form_action = self.request.path
        submit_class = "btn-default disabled" if not self.fields['team'].queryset.exists() else "btn-primary"

        self.helper.layout = Layout(
            Div(
                Div(
                    HTML(
                        "<div class='alert alert-info'>"
                        "<strong>{{project}}</strong>: {{session.start}} &mdash; {{session.end}}"
                        "</div>"
                    ),
                    Div(
                        Div(InlineCheckboxes('samples', template="projects/fields/%s/sample-selection.html"),
                            css_class="col-sm-12 sample-list"),
                        Div(InlineCheckboxes("team"), css_class="col-sm-12"),
                        Div(Field("staff", css_class="chosen"), css_class="col-sm-12"),
                        css_class="row narrow-gutter"
                    ),
                    css_class="col-xs-12"
                ),
                css_class="row modal-scroll-body"
            ),
            Div(
                Div(
                    StrictButton('Cancel', type='button', data_dismiss='modal', css_class="btn btn-default pull-left"),
                    StrictButton('Sign-On', type='submit', value='Save',
                                 css_class='btn pull-right {}'.format(submit_class)),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            )
        )

    def clean(self):
        from agreements.models import Agreement
        data = super().clean()
        team = data.get('team')
        samples = data.get('samples', [])
        failures = []
        joiner = Joiner(', ', ' & ')

        # Get required permissions from approved material if it exists
        material = self.material
        req_perms = set()
        any_perms = set()
        user_perms = set()
        if material:
            req_perms |= {k for k, v in list(material.permissions.items()) if v == 'all'}
            any_perms |= {k for k, v in list(material.permissions.items()) if v == 'any'}
        else:
            msg = (
                "Materials have not been approved. Approved materials are required to use the beamline "
                "even if no samples will actually be used."
            )

            failures.append(msg)

        # Local access needs 'FACILITY-ACCESS' permissions and different USER type from Remote
        if self.session.kind != self.session.TYPES.remote:
            req_perms |= {'FACILITY-ACCESS'}
            user_perms |= {'{}-USER'.format(self.session.beamline)}
            remote = False
        else:
            user_perms |= {'{}-REMOTE-USER'.format(self.session.beamline)}
            remote = True

        # fetch per sample permissions and check ethics for each sample
        ethics_problems = []
        for s in samples:
            req_perms |= {k for k, v in list(s.sample.permissions().items()) if v == 'all'}
            any_perms |= {k for k, v in list(s.sample.permissions().items()) if v == 'any'}
            if s.expiry and s.expiry < self.session.end.date():
                ethics_problems.append(s)
        if ethics_problems:
            self.add_error('Ethics expires before session.')
            msg = (
                'All samples requiring ethics must have valid certificates for the duration of the session. '
                'The following samples will expire during the session: {}'.format(joiner(ethics_problems))
            )
            raise forms.ValidationError(msg, code='invalid')

        # Test qualifications of team members
        if team:
            missing_agreements = [
                f'{member}'
                for member in team
                if (
                    Agreement.objects.pending_for_user(member).exists()
                    and member.institution
                    and not member.institution.state == member.institution.STATES.exempt
                )
            ]

            if missing_agreements:
                msg = (
                    "All participating team members must have valid User Agreements. "
                    "The following users do not: {}.".format(
                        joiner(missing_agreements)
                    )
                )
                self.add_error('team', 'Unqualified users selected.')
                failures.append(msg)

            students = [
                member for member in team
                if member.has_role('high-school-student')
            ]
            # Test if student is signing on to non-education project
            if students and material.project.kind != material.project.TYPES.education:
                msg = (
                    "High school students are not allowed on non-education projects. "
                    "The following users are affected: {}.".format(
                        joiner(students)
                    )
                )
                self.add_error('team', 'High school students selected.')
                failures.append(msg)

            unqualified = [
                member
                for member in team
                if not (
                        member.has_all_perms(*req_perms) and
                        self.session.beamline.is_user(member, remote=remote)
                )
            ]
            if unqualified:
                req_perms |= user_perms
                msg = (
                    "Your planned use of {} requires {} permissions for all participating team members. The following "
                    "selected team members did not qualify: {}.".format(
                        self.session.beamline, joiner(req_perms), joiner(unqualified)
                    )
                )
                self.add_error('team', 'Unqualified users selected.')
                failures.append(msg)

            team_perms = set()
            for member in team:
                team_perms |= set(member.get_all_permissions())
            if not (team_perms >= any_perms):
                self.add_error('team', 'Team requirements not met.')
                msg = 'At least one team member must have {} permissions.'.format(joiner(any_perms - team_perms))
                failures.append(msg)
        if failures:
            raise forms.ValidationError(mark_safe('<br/>'.join(failures)), code='invalid')
        return data


class TeamForm(DynFormMixin, forms.ModelForm):
    type_code = 'team'
    details = forms.Field(required=False)

    class Meta:
        model = models.Project
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_fields()

    def _custom_clean(self, data):
        data['active_page'] = '1'
        return super()._custom_clean(data)


class AllocationForm(forms.ModelForm):
    last_cycle = forms.ModelChoiceField(label="Expiry Cycle", queryset=ReviewCycle.objects.all(), required=False,
                                        help_text="Change this to limit the project duration")

    class Meta:
        model = models.Allocation
        fields = ['shifts', 'beamline', 'cycle', 'project', 'comments']
        widgets = {
            'cycle': forms.HiddenInput,
            'project': forms.HiddenInput,
            'beamline': forms.HiddenInput,
            'comments': forms.Textarea(attrs={'rows': 2, }),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)

        self.fields['last_cycle'].queryset = ReviewCycle.objects.filter(pk__gte=self.initial['cycle'])

        self.helper = FormHelper()
        self.helper.form_action = self.request.get_full_path()
        self.helper.title = 'Allocate Beamtime'
        self.helper.layout = Layout(
            Div(
                Div(
                    'cycle', 'beamline', 'project',
                    Div('shifts', css_class="col-sm-12"),
                    Div('comments', css_class="col-xs-12"),
                    Div(Field('last_cycle', css_class="chosen"), css_class="col-sm-12"),
                    css_class="col-xs-12 narrow-gutter"
                ),
                css_class="row"
            ),
            Div(
                Div(
                    Div(
                        StrictButton('Submit', type='submit', value='Save', css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            )
        )


class ReservationForm(forms.ModelForm):
    class Meta:
        model = models.Reservation
        fields = ['shifts', 'comments']
        widgets = {
            'comments': forms.Textarea(attrs={'rows': 2, }),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_action = self.request.get_full_path()
        self.helper.title = 'Reserve Beamtime'
        self.helper.layout = Layout(
            Div(
                Div(
                    Div('shifts', css_class="col-sm-12"),
                    Div('comments', css_class="col-xs-12"),
                    css_class="col-xs-12 narrow-gutter"
                ),
                css_class="row"
            ),
            Div(
                Div(
                    Div(
                        StrictButton('Submit', type='submit', value='Save', css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            )
        )


class ShiftRequestForm(forms.ModelForm):
    shift_request = forms.IntegerField(
        label="Number of shifts requested",
        required=True,
        widget=forms.NumberInput()
    )
    justification = forms.CharField(
        required=True,
        help_text="Please justify the number of shifts requested",
        widget=forms.Textarea(attrs={'rows': 6, }),
    )
    comments = forms.CharField(
        required=True,
        help_text="Describe specific requirements that might be relevant when scheduling your beamtime. "
                  "Use the scheduling tags above for more general requirements",
        widget=forms.Textarea(attrs={'rows': 4, })
    )
    tags = forms.ModelMultipleChoiceField(label="Scheduling Tags", required=False, queryset=FacilityTag.objects)
    good_dates = forms.CharField(required=False, label="Preferred Dates")
    poor_dates = forms.CharField(required=False, label="Undesirable Dates")

    class Meta:
        model = models.ShiftRequest
        fields = ['shift_request', 'justification', 'comments', 'tags',
                  'good_dates', 'poor_dates']

    def __init__(self, *args, **kwargs):
        self.facility = kwargs.pop('facility', None)
        title = kwargs.pop('form_title', "Edit Request")
        super().__init__(*args, **kwargs)
        self.fields['tags'].queryset = self.facility.tags()
        self.helper = FormHelper()
        self.helper.title = title
        self.helper.layout = Layout(
            Div(
                Div('shift_request', css_class="col-sm-6"),
                Div(Field('tags', css_class="chosen"), css_class="col-sm-6"),
                Div('justification', css_class="col-xs-12"),
                Div('comments', css_class="col-xs-12"),
                Div(
                    PrependedText(
                        "good_dates",
                        mark_safe('<i class="bi-calendar-check-fill text-success"></i>'),
                        css_class="dateinput",
                        data_date_container="#div_id_good_dates"
                    ),
                    css_class="col-sm-6"
                ),
                Div(
                    PrependedText(
                        "poor_dates",
                        mark_safe('<i class="bi-calendar-minus text-danger"></i>'),
                        css_class="dateinput",
                        data_date_container="#div_id_poor_dates"
                    ),
                    css_class="col-sm-6"
                ),
                css_class="row narrow-gutter"
            ),
            Div(
                Div(
                    Div(
                        StrictButton('Save', name="form_action", type='submit', value='save',
                                     css_class='btn btn-default'),
                        StrictButton('Submit', name="form_action", type='submit', value='submit',
                                     css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            )
        )

    def clean(self):
        data = super().clean()
        data['form_action'] = self.data.get('form_action')
        return data


class AllocRequestForm(ShiftRequestForm):
    class Meta:
        model = models.AllocationRequest
        fields = ['shift_request', 'justification', 'comments', 'tags',
                  'good_dates', 'poor_dates']


class DeclineForm(forms.ModelForm):
    comments = forms.CharField(
        label="Please explain why you are declining the allocated shifts",
        widget=forms.Textarea(attrs={'rows': 3, }),
    )

    class Meta:
        model = models.Allocation
        fields = ['comments']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.title = "Decline Allocation"
        self.helper.form_action = self.request.path
        self.helper.layout = Layout(
            Div(
                Div(
                    HTML(
                        "<div class='minitron bg-danger text-default'>"
                        "<h3>Are you sure?</h3>"
                        "<p>By declining this allocation, you are declaring you do not intend to use any of "
                        "your remaining allocated shifts for project <strong>{{allocation.project.code}}</strong> on "
                        "beamline <strong>{{allocation.beamline}}</strong> during the {{allocation.cycle}} cycle.</p> "
                        "<p><strong>NOTE:</strong> (1) All outstanding scheduled beamtime on <strong>{{allocation.beamline}}</strong> "
                        "will be cancelled. (2) Declined shifts will be reallocated and it may not be possible to reclaim them."
                        "(3) You will be able to renew the project by requesting another allocation on this beamline during the next cycle. "
                        "However, you will not be entitled to any score bumps for not having used beamtime during the {{allocation.cycle}} cycle. </p>"
                        "</div>"
                    ),
                ),
                Field("comments", css_class="col-sm-12"),
                css_class="row modal-body"
            ),
            Div(css_class="modal-body"),
            Div(
                Div(
                    StrictButton('Cancel', type='button', data_dismiss='modal', css_class="btn btn-default pull-left"),
                    StrictButton('Yes, Decline', type='submit', value='decline',
                                 css_class='btn btn-primary pull-right'),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            )
        )


class TerminationForm(forms.ModelForm):
    reason = forms.CharField(
        label="Please explain why you are terminating the session",
        widget=forms.Textarea(attrs={'rows': 3, }),
        required=True,
    )

    class Meta:
        model = models.Session
        fields = ['reason']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.title = "Terminate Session?"
        self.helper.form_action = self.request.path
        self.helper.layout = Layout(
            Div(
                Div(
                    HTML(
                        "<div class='minitron bg-danger text-default'>"
                        "<h3>Are you sure you want to terminate the session:</h3>"
                        "<h5><strong>{{session}}</strong>: {{session.start}} &mdash; {{session.end}}</h5>"
                        "<p>By terminating the session, you are declaring that the users are no longer "
                        "permitted to use the beamline and administrative steps have been or will be taken to enforce that. "
                        "<p><strong>NOTE:</strong> (1) Termination should only be done during extra-ordinary circumstances "
                        "and should not be used to sign-off users from an active session. "
                        "(2) Beamline Staff will be notified of all terminations. </p>"
                        "</div>"
                    ),
                ),
                Field("reason", css_class="col-sm-12"),
                css_class="row modal-body"
            ),
            Div(css_class="modal-body"),
            Div(
                Div(
                    StrictButton('Cancel', type='button', data_dismiss='modal', css_class="btn btn-default pull-left"),
                    StrictButton('Yes, Terminate', type='submit', value='decline',
                                 css_class='btn btn-primary pull-right'),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            )
        )
