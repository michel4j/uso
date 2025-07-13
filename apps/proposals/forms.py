import itertools
from itertools import chain

from crisp_modals.forms import ModalModelForm, ModalForm
from crispy_forms.bootstrap import StrictButton, AppendedText, InlineCheckboxes, FormActions, InlineRadios
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, HTML
from django import forms
from django.db.models import Q, Count
from django.forms.models import ModelChoiceField
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from dynforms.forms import DynModelForm
from dynforms.utils import DotExpandedDict

from misc.forms import JSONDictionaryField, ModelPoolField
from . import models
from . import utils
from .models import get_user_model
from beamlines.models import Facility


class DateField(AppendedText):
    def __init__(self, field_name, *args, **kwargs):
        super().__init__(field_name, mark_safe('<i class="bi-calendar"></i>'), *args, **kwargs)


class ProposalForm(DynModelForm):
    class Meta:
        model = models.Proposal
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        user_model = get_user_model()
        data = super().clean()
        data['title'] = data['details'].get('title')
        if not data['title']:
            self._errors['title'] = "You must add a title before you can save the proposal "

        subjects = data['details'].get('subject', {})
        if isinstance(subjects, list) and len(subjects) == 1:
            subjects = subjects[0]
        else:
            subjects = subjects or {}

        data['keywords'] = subjects.get('keywords', '').strip()
        team_members = data['details'].get('team_members', [])[:]  # make a copy to avoid modifying in-place
        existing_emails = []
        for k in ['leader', 'delegate']:
            if k in data['details']:
                m = data['details'][k]
                user_email = m.get('email', 'xxx')
                user = user_model.objects.filter(Q(email__iexact=user_email) | Q(alt_email__iexact=user_email)).first()
                if user:
                    data[f"{k}_username"] = user.username
                existing_emails.append(user_email)
                team_members.append(m)

        # Remove duplicates
        data['details']['team_members'] = [
            tm for tm in data['details'].get('team_members', [])
            if tm.get('email') not in existing_emails
        ]
        data['team'] = [_f for _f in {p.get('email', '').lower() for p in team_members} if _f]
        return data


class ReviewForm(DynModelForm):
    class Meta:
        model = models.Review
        fields = []


class ReviewerForm(forms.Form):
    techniques = forms.ModelMultipleChoiceField(
        queryset=models.Technique.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    areas = forms.ModelMultipleChoiceField(
        label="Main Areas",
        queryset=models.SubjectArea.objects.none(),
        required=False
    )
    sub_areas = forms.ModelMultipleChoiceField(
        label=_("Sub-areas"),
        queryset=models.SubjectArea.objects.none(),
        required=False
    )

    def __init__(self, *args, **kwargs):
        admin = kwargs.pop('admin', False)
        super().__init__(*args, **kwargs)

        techs = {}
        for kind in models.Technique.objects.all().values_list('category', flat=True).distinct():
            if kind:
                qs = models.Technique.objects.filter(category=kind)
                self.fields[kind] = forms.ModelMultipleChoiceField(
                    label=models.Technique.TYPES[kind],
                    queryset=qs,
                    widget=forms.CheckboxSelectMultiple,
                    required=False
                )
                techs[kind] = qs.count()
                if 'techniques' in self.initial:
                    self.fields[kind].initial = self.initial['techniques'].filter(category=kind)
        self.fields['areas'].queryset = models.SubjectArea.objects.filter(category__isnull=True).order_by('name')
        self.fields['sub_areas'].queryset = models.SubjectArea.objects.exclude(category__isnull=True).order_by('name')
        tech_fields = Div(
            Div(
                HTML(
                    '<h3>Techniques</h3>'
                    '<hr class="hr-xs"/>'
                ),
                css_class="col-sm-12"
            ),
            css_class="row"
        )

        for tech, count in sorted(list(techs.items()), key=lambda v: v[1], reverse=True):
            tech_fields.append(
                Div(
                    tech,
                    css_class="col-sm-12 field-w2"
                )
            )

        reviewer = self.initial.get('reviewer')
        if admin:
            if reviewer and reviewer.active:
                disable_btn = StrictButton(
                    'Disable Reviewer', type='submit', name="submit", value='disable',
                    css_class="btn btn-danger"
                )
            else:
                disable_btn = StrictButton(
                    'Enable Reviewer', type='submit', name="submit", value='enable',
                    css_class="btn btn-warning"
                )

            if reviewer and reviewer.is_suspended():
                suspend_btn = StrictButton(
                    'Reinstate Reviewer', type='submit', name="submit", value='reinstate',
                    css_class="btn btn-info"
                )
            else:
                suspend_btn = StrictButton(
                    'Opt Out', type='submit', name="submit", value='suspend',
                    css_class="btn btn-secondary"
                )
            extra_btns = Div(
                disable_btn,
                suspend_btn,
                css_class="pull-left"
            )

        else:
            extra_btns = Div(css_class="pull-left")

        self.helper = FormHelper()
        if reviewer:
            self.helper.title = f"Edit {reviewer.user.get_full_name()}'s Reviewer Profile"
        else:
            self.helper.title = "Add Reviewer Profile"
        self.helper.layout = Layout(
            Div(
                Div(
                    HTML(
                        '<h3>Subject Areas</h3>'
                        '<hr class="hr-xs"/>'
                    ),
                    css_class="col-sm-12"
                ),

                Div(Field('areas', css_class="selectize"), css_class="col-sm-12"),
                Div(
                    InlineCheckboxes('sub_areas', template="proposals/fields/%s/groupedcheckboxes.html"),
                    css_class="col-sm-12"
                ),
                css_class="row"
            ),

            tech_fields,
            FormActions(
                HTML("<hr/>"),
                extra_btns,
                Div(
                    StrictButton('Revert', type='reset', value='Reset', css_class="btn btn-secondary"),
                    StrictButton('Save', type='submit', name="submit", value='save', css_class='btn btn-primary'),
                    css_class='pull-right'
                ),
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        for tech in models.Technique.TYPES:
            cleaned_data['techniques'] = list(
                chain(cleaned_data.get(tech[0], []), cleaned_data['techniques'])
            )
        cleaned_data['areas'] = list(
            chain(
                cleaned_data.get('areas', []),
                [sa for sa in cleaned_data.get('sub_areas', []) if sa.category in cleaned_data.get('areas', [])]
            )
        )
        return cleaned_data


class OptOutForm(ModalModelForm):
    class Meta:
        model = models.Reviewer
        fields = ['comments']
        widgets = {
            'comments': forms.Textarea(attrs={'rows': 3, }),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)
        self.body.title = "We're sorry to miss you this time around!"
        self.body.form_class = "call-form"
        self.body.form_action = self.request.get_full_path()
        self.body.append(
            Div(
                Div(
                    Div(
                        HTML("{% include 'proposals/forms/optout-header.html' %}"),
                        css_class="col-sm-12"
                    ),
                    Div('comments', css_class="col-sm-12"),
                    css_class="col-sm-12 gap-2"
                ),
                css_class="row"
            )
        )


class FacilityConfigForm(ModalModelForm):
    configs = forms.Field(required=False)
    accept = forms.TypedChoiceField(
        label="Accepting Proposals?",
        coerce=lambda x: x == 'True',
        choices=((False, 'No'), (True, 'Yes')), widget=forms.RadioSelect)

    class Meta:
        model = models.FacilityConfig
        fields = ['comments', 'facility', 'accept', 'cycle', 'configs']
        widgets = {
            'comments': forms.Textarea(attrs={'rows': 3, }),
            'facility': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)
        today = timezone.now().date()
        self.fields['cycle'].queryset = models.ReviewCycle.objects.filter(open_date__gt=today)
        if self.instance and self.instance.pk:
            if self.instance.cycle is None:
                self.fields['cycle'].disabled = True
            elif self.instance.cycle.start_date < today:
                self.fields['cycle'].disabled = True
                self.fields['cycle'].queryset |= models.ReviewCycle.objects.filter(pk=self.instance.cycle.pk)

        self.body.title = 'Configure Technique Availability'
        self.body.form_action = self.request.get_full_path()
        self.body.append(
            Div(
                Div(
                    Field('cycle', css_class="selectize"),
                    css_class="col-sm-6"
                ),
                Div(
                    InlineRadios('accept'),
                    css_class="col-sm-6"
                ),
                css_class="row"
            ),
            'facility',
            Div(
                Field('configs', template="proposals/fields/facilityconfig.html"),
                style="margin-top: 0.5em;"
            ),
            'comments',
        )

    def clean(self):
        data = super().clean()
        raw_configs = DotExpandedDict(dict(self.data.lists())).with_lists().get('configs', {})
        configs = {
            (int(item['technique'][0]), int(v))
            for item in raw_configs if 'value' in item and 'technique' in item
            for v in item['value']
        }
        data['configs'] = list(configs)
        data['start_date'] = data['cycle'].start_date
        return data


class ReviewCycleForm(ModalModelForm):
    class Meta:
        model = models.ReviewCycle
        fields = ('start_date', 'open_date', 'close_date', 'end_date', 'due_date', 'alloc_date')

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)
        self.body.form_action = self.request.get_full_path()
        self.body.title = "Configure Review Cycle"

        self.body.append(
            Div(
                Div(DateField("start_date"), css_class="col-sm-6"),
                Div(DateField("end_date"), css_class="col-sm-6"),
                Div(DateField("open_date"), css_class="col-sm-6"),
                Div(DateField("close_date"), css_class="col-sm-6"),
                Div(DateField("due_date"), css_class="col-sm-6"),
                Div(DateField("alloc_date"), css_class="col-sm-6"),
                css_class="row"
            )
        )


class ReviewTrackForm(ModalModelForm):
    committee = forms.ModelMultipleChoiceField(queryset=models.Reviewer.objects.all(), required=False)

    class Meta:
        model = models.ReviewTrack
        fields = (
            'name', 'acronym', 'description', 'require_call',
            'committee', 'duration'
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, }),
        }
        help_texts = {
            'duration': 'Duration of resulting Project in cycles',
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.body.form_class = "review-track-form"
        self.body.append(
            Div(
                Div("name", css_class="col-sm-8"),
                Div("acronym", css_class="col-sm-4"),
                Div("description", css_class="col-sm-12"),
                Div("duration", css_class="col-sm-12"),
                Div("committee", css_class="col-sm-12"),
                Div("require_call", css_class="col-sm-12"),
                css_class="row"
            )
        )


class ReviewCyclePoolForm(forms.ModelForm):
    class Meta:
        model = models.ReviewCycle
        fields = ('reviewers',)
        widgets = {
            'reviewers': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "review-cycle-form"
        self.helper.title = "Edit Reviewer Pool for Cycle {0}".format(self.instance)

        self.helper.layout = Layout(
            Div(
                Div(InlineCheckboxes('reviewers'), css_class="col-sm-12"),
                css_class="row"
            ),
            Div(
                Div(
                    Div(
                        StrictButton('Revert', type='reset', value='Reset', css_class="btn btn-secondary"),
                        StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-sm-12"
                ),
                css_class="modal-footer row"
            )
        )


class ReviewerAssignmentForm(ModalModelForm):
    reviewers = forms.ModelMultipleChoiceField(
        label="Add Reviewer", queryset=models.Reviewer.objects.none(),
        help_text="Select Reviewers to add to the above proposal. "
                  "The list shows compatible reviewers who have room to review more proposals"
    )

    class Meta:
        model = models.Submission
        fields = []

    def __init__(self, *args, **kwargs):
        stage = kwargs.pop('stage')
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()

        self.body.title = "Edit Reviewer Assignment"

        cycle = self.instance.cycle
        track = stage.track

        prop_info = utils.get_submission_info(self.instance)
        tech_filter = Q(techniques__in=prop_info['techniques'])
        area_filter = Q(areas__in=prop_info['areas'])

        reviewers = models.Reviewer.objects.available(cycle).filter(tech_filter, area_filter)
        reviewers = reviewers.annotate(
            num_reviews=Count('user__reviews', filter=Q(user__reviews__cycle=cycle), distinct=True)
        )

        if stage.max_workload > 0:
            reviewers = reviewers.exclude(num_reviews__gt=stage.max_workload)

        available = models.Reviewer.objects.filter(pk__in=list(
            itertools.chain(reviewers.values_list('pk', flat=True), track.committee.values_list('pk', flat=True))
        )).order_by('committee')

        self.fields['reviewers'].queryset = available
        self.body.title = 'Add Reviewers'
        self.body.append(
            Div(
                HTML("{% include 'proposals/submission-snippet.html' with submission=form.instance %}"),
                css_class=""
            ),
            Div(
                Div(Field('reviewers', css_class="selectize"), css_class='col-sm-12'),
                css_class="row"
            )
        )


class AdjustmentForm(ModalModelForm):
    VALUE_TYPES = (
        (-1, '-1.0'),
        (-0.5, '-0.5'),
        (0.5, '+0.5'),
        (1, '+1.0'),
    )
    value = forms.TypedChoiceField(choices=VALUE_TYPES, empty_value="0.0", coerce=float, label=_('Score Adjustment'))

    class Meta:
        model = models.ScoreAdjustment
        fields = ('value', 'reason')

        widgets = {
            'reason': forms.Textarea(attrs={'rows': 3, }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['value'].choices = self.VALUE_TYPES
        self.fields['reason'].help_text = 'Please provide an explanation justifying the score adjustment'
        self.body.append(
            Div(
                Div(Field('value', css_class="selectize"), css_class="col-sm-12"),
                Div("reason", css_class="col-sm-12"),
                css_class="row"
            ),
        )


class ReviewCommentsForm(ModalModelForm):
    class Meta:
        model = models.Submission
        fields = ['comments']

        widgets = {
            'comments': forms.Textarea(attrs={'rows': 12, }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['comments'].help_text = 'Please update the comments which the applicants will see.'
        self.body.title = "Update Comments for Applicants"
        self.body.append(
            Div(
                Div("comments", css_class="col-sm-12"),
                css_class="row"
            ),
        )


class ReviewStageForm(ModalModelForm):
    class Meta:
        model = models.ReviewStage
        fields = [
            'track', 'kind', 'position', 'min_reviews', 'blocks', 'pass_score',
            'auto_create', 'auto_start', 'weight'
        ]
        widgets = {
            'track': forms.HiddenInput(),
            'kind': forms.Select(attrs={'class': 'select'}),
            'blocks': forms.Select(choices=((False, 'No'), (True, 'Yes')), attrs={'class': 'select'}, ),
            'auto_create': forms.Select(choices=((False, 'No'), (True, 'Yes')), attrs={'class': 'select'}, ),
            'auto_start': forms.Select(choices=((False, 'No'), (True, 'Yes')), attrs={'class': 'select'}, ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not (self.instance and self.instance.pk):
            track = self.initial['track']
            self.fields['kind'].queryset = models.ReviewType.objects.exclude(stages__track=track)

        self.body.append(
            Div(
                Div("position", css_class="col-sm-3"),
                Div("kind", css_class="col-sm-6"),
                Div("weight", css_class="col-sm-3"),
                Div("min_reviews", css_class="col-sm-6"),
                Div("pass_score", css_class="col-sm-6"),
                Div("blocks", css_class="col-sm-4"),
                Div("auto_create", css_class="col-sm-4"),
                Div("auto_start", css_class="col-sm-4"),
                css_class="row"
            ),
            Field('track'),
        )


class ReviewTypeForm(ModalModelForm):
    score_fields = JSONDictionaryField(label=_("Score Fields"), required=False)

    class Meta:
        model = models.ReviewType
        fields = [
            'code', 'kind', 'description', 'form_type', 'low_better', 'per_facility', 'role',
            'score_fields'
        ]
        widgets = {
            'description': forms.TextInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.body.append(
            Div(
                Div("code", css_class="col-sm-4"),
                Div("kind", css_class="col-sm-4"),
                Div("form_type", css_class="col-sm-4"),
                Div("description", css_class="col-sm-8"),
                Div("role", css_class="col-sm-4"),
                css_class="row"
            ),
            Div(

                Div("score_fields", css_class="col-sm-12"),
                css_class="row"
            ),
            Div(
                Div('low_better', css_class="col-sm-4"),
                Div('per_facility', css_class="col-sm-4"),
                css_class="row align-items-end"
            )
        )

    def clean(self):
        data = super().clean()
        score_field_names = set(data.get('score_fields', {}).keys())
        form_field_names = set([
            field['name']
            for page in data['form_type'].pages
            for field in page.get('fields', [])
        ])
        missing_fields = score_field_names - form_field_names
        if missing_fields:
            missing_text = ', '.join(f'"{field}"' for field in missing_fields)
            raise forms.ValidationError(
                f"Score fields {missing_text} not defined in {data['form_type']}."
            )
        return data


class TechniqueForm(ModalModelForm):
    class Meta:
        model = models.Technique
        fields = ['name', 'category', 'description', 'acronym', 'parent']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.body.append(
            Div(
                Div("name", css_class="col-sm-6"),
                Div("acronym", css_class="col-sm-6"),
                Div("category", css_class="col-sm-6"),
                Div("parent", css_class="col-sm-6"),
                Div("description", css_class="col-sm-12"),
                css_class="row"
            )
        )


class AccessPoolForm(ModalModelForm):
    class Meta:
        model = models.AccessPool
        fields = ['name', 'description', 'role']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.body.append(
            Div(
                Div("name", css_class="col-sm-6"),
                Div("role", css_class="col-sm-6"),
                Div("description", css_class="col-sm-12"),
                css_class="row"
            )
        )


class AllocationPoolForm(ModalModelForm):
    pools = ModelPoolField(model='proposals.AccessPool', required=False, label="Pool Allocations")

    class Meta:
        fields = ['flex_schedule']
        model = Facility

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.body.title = f"Pool Allocations - {self.instance.acronym}"
        self.body.append(
            Div(
                Div('flex_schedule', css_class="col-sm-12"),
                Div('pools', css_class="col-sm-12"),
                css_class="row"
            )
        )


class SubmitProposalForm(ModalModelForm):
    access_pool = forms.ModelChoiceField(
        queryset=models.AccessPool.objects.none(), required=True, label="Access Pool",
    )
    tracks = forms.ModelMultipleChoiceField(
        queryset=models.ReviewTrack.objects.none(), required=True, label="Review Tracks",
    )

    class Meta:
        model = models.Proposal
        fields = ['access_pool', 'tracks']

    def __init__(self, submit_info=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.body.title = "Submit Proposal"
        self.body.append(
            Div(
                Div(
                    HTML("{% include 'proposals/forms/submit-header.html' %}"),
                    css_class="col-sm-12"
                ),
                Div('tracks', css_class="col-sm-6"),
                Div('access_pool', css_class="col-sm-6"),
                css_class="row"
            )
        )
        self.fields['access_pool'].initial = submit_info['pools'].filter(is_default=True).first()
        valid_tracks = submit_info['valid_tracks']
        self.fields['access_pool'].queryset = submit_info['pools']
        self.fields['tracks'].queryset = models.ReviewTrack.objects.filter(pk__in=valid_tracks)
        if len(valid_tracks) == 1:
            self.fields['tracks'].initial = models.ReviewTrack.objects.filter(pk__in=valid_tracks)
            self.fields['tracks'].disabled = True
        if len(submit_info['pools']) == 1:
            self.fields['access_pool'].disabled = True

        self.footer.clear()
        if len(valid_tracks) == 0:
            self.footer.append(
                StrictButton('Cancel', type='button', data_bs_dismiss='modal', css_class="btn btn-secondary"),
            )
        else:
            self.footer.append(
                StrictButton('Cancel', type='button', data_bs_dismiss='modal', css_class="btn btn-secondary"),
                StrictButton('Submit Proposal', type='submit', value='submit', css_class="ms-auto btn btn-primary"),
            )
