import functools
import itertools
import operator
import time
from itertools import chain

from crisp_modals.forms import ModalModelForm, FullWidth, Row
from crispy_forms.bootstrap import StrictButton, AppendedText, InlineCheckboxes, FormActions, InlineRadios
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, HTML
from django import forms
from django.urls import reverse
from django.db.models import Case, When, Q, IntegerField, Sum, Value, Count
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from . import models
from . import utils
from dynforms.forms import DynFormMixin, DynModelForm
from dynforms.utils import DotExpandedDict
from .models import get_user_model


class DateField(AppendedText):
    def __init__(self, field_name, *args, **kwargs):
        super().__init__(field_name, mark_safe('<i class="bi-calendar"></i>'), *args, **kwargs)


class ProposalForm(DynModelForm):
    type_code = 'proposal'

    class Meta:
        model = models.Proposal
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_fields()

    def clean(self):
        User = get_user_model()
        data = super().clean()
        data['title'] = data['details'].get('title')
        if not data['title']:
            self._errors['title'] = "You must add a title before you can save the proposal "
        data['keywords'] = data['details'].get('subject', {}).get('keywords')
        team_members = data['details'].get('team_members', [])[:]  # make a copy to avoid modifying in-place
        existing_emails = []
        for k in ['leader', 'delegate']:
            if k in data['details']:
                m = data['details'][k]
                user_email = m.get('email', 'xxx')
                user = User.objects.filter(Q(email__iexact=user_email) | Q(alt_email__iexact=user_email)).first()
                if user:
                    data["{}_username".format(k)] = user.username
                existing_emails.append(user_email)
                team_members.append(m)

        # Remove duplicates
        data['details']['team_members'] = [
            tm for tm in data['details'].get('team_members', [])
            if tm.get('email') not in existing_emails
        ]
        data['team'] = [_f for _f in {p.get('email', '').lower() for p in team_members} if _f]
        return data


class ReviewForm(DynFormMixin, forms.ModelForm):
    class Meta:
        model = models.Review
        fields = []

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        if self.instance:
            self.form_type = self.instance.form_type
        self.init_fields()

    def clean(self):
        return DynFormMixin.clean(self)


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
                css_class="col-xs-12"
            ),
            css_class="row"
        )

        for tech, count in sorted(list(techs.items()), key=lambda v: v[1], reverse=True):
            tech_fields.append(
                Div(
                    tech,
                    css_class="col-xs-12 field-w2"
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
                    css_class="col-xs-12"
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
                        css_class="col-xs-12"
                    ),
                    Div('comments', css_class="col-xs-12"),
                    css_class="col-xs-12 gap-2"
                ),
                css_class="row"
            )
        )


class FacilityConfigForm(ModalModelForm):
    settings = forms.Field(required=False)
    accept = forms.TypedChoiceField(
        label="Accepting Proposals?",
        coerce=lambda x: x == 'True',
        choices=((False, 'No'), (True, 'Yes')), widget=forms.RadioSelect)

    class Meta:
        model = models.FacilityConfig
        fields = ['comments', 'facility', 'accept', 'cycle', 'settings']
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
            self.fields['cycle'].queryset |= models.ReviewCycle.objects.filter(pk=self.instance.cycle.pk)
            if self.instance.cycle.open_date <= today:
                self.fields['cycle'].disabled = True

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
                Field('settings', template="proposals/fields/facilityconfig.html"),
                style="margin-top: 0.5em;"
            ),
            'comments',
        )

    def clean(self):
        data = super().clean()
        raw_settings = DotExpandedDict(self.data).with_lists().get('settings', {})
        settings = list(zip(raw_settings.get('technique', []), raw_settings.get('value', [])))
        data['settings'] = {int(k): v for k, v in settings if v}
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
        fields = ('name', 'acronym', 'description',
                  'min_reviewers', 'max_workload', 'committee')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, }),
        }
        help_texts = {
            'min_reviewers': 'Committee members per proposal',
            'max_workload': 'Maximum reviewer workload',
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.body.form_class = "review-track-form"
        self.body.form_action = self.request.get_full_path()
        self.body.title = "Edit Review Track Information"

        self.body.append(
            Div(
                Div("name", css_class="col-sm-8"),
                Div("acronym", css_class="col-sm-4"),
                Div("description", css_class="col-sm-12"),
                Div("min_reviewers", css_class="col-sm-6"),
                Div("max_workload", css_class="col-sm-6"),
                Div(Field("committee", css_class="selectize"), css_class="col-sm-12"),
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
                    css_class="col-xs-12"
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
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()

        self.body.title = "Edit Reviewer Assignment"
        self.body.form_action = self.request.get_full_path()

        cycle = self.instance.cycle
        track = self.instance.track

        prop_info = utils.get_submission_info(self.instance)
        tech_filter = Q(techniques__in=prop_info['techniques'])
        area_filter = Q(areas__in=prop_info['areas'])

        reviewers = models.Reviewer.objects.available(cycle).filter(tech_filter, area_filter)
        reviewers = reviewers.annotate(
            num_reviews=Count('user__reviews', filter=Q(user__reviews__cycle=cycle), distinct=True)
        )

        if track.max_workload > 0:
            reviewers = reviewers.exclude(num_reviews__gt=track.max_workload)

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


class AdjustmentForm(forms.ModelForm):
    VALUE_TYPES = (
        (-1, '-1.0'),
        (-0.5, '-0.5'),
        (0.5, '+0.5'),
        (1, '+1.0'),
    )
    value = forms.TypedChoiceField(
        choices=VALUE_TYPES, empty_value=0, coerce=float)

    class Meta:
        model = models.ScoreAdjustment
        fields = ('value', 'reason')

        widgets = {
            'reason': forms.Textarea(attrs={'rows': 4, }),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        self.submission = kwargs.pop('submission')
        super().__init__(*args, **kwargs)

        self.fields['reason'].help_text = 'Please provide an explanation justifying the score adjustment'

        self.helper = FormHelper()
        self.helper.title = "Adjust Score"

        delete_url = reverse("remove-score-adjustment", kwargs={'pk': self.submission.pk})

        self.helper.form_action = self.request.get_full_path()
        self.helper.layout = Layout(
            Div(
                Div(Field('value', css_class="selectize"), css_class="col-sm-12"),
                Div("reason", css_class="col-sm-12"),
                css_class="row"
            ),
            Div(
                Div(
                    StrictButton('Delete', id="delete-object", css_class="btn btn-danger pull-left",
                                 data_url=delete_url),
                    StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary pull-right'),
                    StrictButton('Cancel', type='button', data_dismiss='modal', css_class="btn btn-secondary pull-right"),

                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            ),
        )


class ReviewCommentsForm(forms.ModelForm):
    class Meta:
        model = models.Submission
        fields = ['comments']

        widgets = {
            'comments': forms.Textarea(attrs={'rows': 12, }),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)

        self.fields['comments'].help_text = 'Please update the comments which the applicants will see.'

        self.helper = FormHelper()
        self.helper.title = "Update Comments for Applicants"
        self.helper.form_action = self.request.get_full_path()
        self.helper.layout = Layout(
            Div(
                Div("comments", css_class="col-sm-12"),
                css_class="row"
            ),
            Div(
                Div(
                    Div(
                        StrictButton('Cancel', type='button', data_dismiss='modal', css_class="btn btn-secondary"),
                        StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            ),
        )


class ReviewStageForm(ModalModelForm):
    class Meta:
        model = models.ReviewStage
        fields = ['track', 'kind', 'position', 'min_reviews', 'blocks', 'pass_score']
        widgets = {
            'track': forms.HiddenInput(),
            'kind': forms.Select(attrs={'class': 'select'}),
            'blocks': forms.Select(choices=((False, 'No'), (True, 'Yes')), attrs={'class': 'select'},),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.body.title = "Edit Review Stage Information"
        else:
            track = self.initial['track']
            self.fields['kind'].queryset = models.ReviewType.objects.exclude(stages__track=track)
            self.body.title = "Add Review Stage"

        self.body.form_action = self.request.get_full_path()
        self.body.append(
            Div(
                Div("kind", css_class="col-sm-6"),
                Div("position", css_class="col-sm-6"),
                Div("min_reviews", css_class="col-sm-4"),
                Div("pass_score", css_class="col-sm-4"),
                Div("blocks", css_class="col-sm-4"),
                css_class="row"
            )
        )
