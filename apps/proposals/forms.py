import functools
import operator
from itertools import chain

from crispy_forms.bootstrap import StrictButton, AppendedText, InlineCheckboxes, FormActions, InlineRadios
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, HTML
from django import forms
from django.urls import reverse
from django.db.models import Case, When, Q, IntegerField, Sum, Value
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from . import models
from . import utils
from dynforms.forms import DynFormMixin
from dynforms.utils import DotExpandedDict
from .models import get_user_model


class DateField(AppendedText):
    def __init__(self, field_name, *args, **kwargs):
        super().__init__(field_name, mark_safe('<i class="bi-calendar"></i>'), *args, **kwargs)


class ProposalForm(DynFormMixin, forms.ModelForm):
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
    reviewer = forms.ModelChoiceField(
        queryset=models.Reviewer.objects.all(),
        widget=forms.HiddenInput,
        required=True
    )
    techniques = forms.ModelMultipleChoiceField(
        queryset=models.Technique.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    areas = forms.ModelMultipleChoiceField(
        label="Main Areas",
        queryset=models.SubjectArea.objects.filter(category__isnull=True).order_by('name'),
        required=False
    )
    sub_areas = forms.ModelMultipleChoiceField(
        label=_("Sub-areas"),
        queryset=models.SubjectArea.objects.exclude(category__isnull=True).order_by('name'),
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

        tech_fields = Div(
            Div(
                HTML(
                    '<h3>Techniques</h3>'
                    '<hr class="hr-xs"/>'
                ),
                css_class="col-xs-12"
            ),
            css_class="row narrow-gutter"
        )

        for tech, count in sorted(list(techs.items()), key=lambda v: v[1], reverse=True):
            tech_fields.append(
                Div(
                    tech,
                    css_class="col-xs-12 field-w2"
                )
            )

        if admin:
            if self.initial['reviewer'].active:
                extra_btns = Div(
                    StrictButton('Disable Reviewer', type='submit', name="submit", value='disable',
                                 css_class="btn btn-danger"),
                    css_class="pull-left"
                )
            else:
                extra_btns = Div(
                    StrictButton('Re-Enable Reviewer', type='submit', name="submit", value='enable',
                                 css_class="btn btn-warning"),
                    css_class="pull-left"
                )
        else:
            extra_btns = Div(css_class="pull-left")

        self.helper = FormHelper()
        self.helper.title = "Edit {0}'s Reviewer Profile".format(self.initial['reviewer'].user.get_full_name())
        self.helper.layout = Layout(
            Field('reviewer', readonly=True),
            Div(
                Div(
                    HTML(
                        '<h3>Subject Areas</h3>'
                        '<hr class="hr-xs"/>'
                    ),
                    css_class="col-xs-12"
                ),

                Div(Field('areas', css_class="chosen"), css_class="col-sm-12"),
                Div(
                    InlineCheckboxes('sub_areas', template="proposals/fields/%s/groupedcheckboxes.html"),
                    css_class="col-sm-12"
                ),
                css_class="row narrow-gutter"
            ),

            tech_fields,
            FormActions(
                HTML("<hr/>"),
                extra_btns,
                Div(
                    StrictButton('Revert', type='reset', value='Reset', css_class="btn btn-default"),
                    StrictButton('Save', type='submit', name="submit", value='save', css_class='btn btn-primary'),
                    css_class='pull-right'
                ),
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        for tech in models.Technique.TYPES:
            cleaned_data['techniques'] = list(chain(cleaned_data.get(tech[0], []), cleaned_data['techniques']))
        cleaned_data['areas'] = list(chain(cleaned_data.get('areas', []),
                                           [sa for sa in cleaned_data.get('sub_areas', []) if
                                            sa.category in cleaned_data.get('areas', [])]))
        return cleaned_data


class OptOutForm(forms.Form):
    cycle = forms.ModelChoiceField(
        queryset=models.ReviewCycle.objects.all(),
        label=_("Review Cycle"),
        required=False,
        widget=forms.HiddenInput
    )
    reason = forms.CharField(
        required=False,
        label="Let us know why you are opting out for this round of reviews (optional)"
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.title = "We're sorry to miss you this time around!"
        self.helper.form_class = "call-form"
        self.helper.form_action = self.request.get_full_path()
        self.helper.layout = Layout(
            Div(
                Div(
                    Field('cycle', readonly=True),
                    Div(
                        HTML("{% include 'proposals/forms/optout-header.html' %}"),
                        css_class="col-xs-12"
                    ),
                    Div('reason', css_class="col-xs-12"),
                    css_class="col-xs-12 narrow-gutter"
                ),
                css_class="row"
            ),
            Div(
                Div(
                    Div(
                        StrictButton('Opt Out', type='submit', value='Save', css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            )
        )


class FacilityConfigForm(forms.ModelForm):
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

        self.helper = FormHelper()
        self.helper.title = 'Configure Technique Availability'
        self.helper.form_action = self.request.get_full_path()
        self.helper.layout = Layout(
            Div(
                Div(
                    Field('cycle', css_class='chosen'),
                    css_class="col-sm-6"
                ),
                Div(
                    InlineRadios('accept'),
                    css_class="col-sm-6"
                ),
                css_class="row narrow-gutter"
            ),
            'facility',
            Div(
                Field('settings', template="proposals/fields/%s/facilityconfig.html"),
                style="margin-top: 0.5em;"
            ),
            'comments',
            Div(
                Div(
                    Div(
                        StrictButton('Cancel', type='button', data_dismiss='modal', css_class="btn btn-default"),
                        StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            )
        )

    def clean(self):
        data = super().clean()
        raw_settings = DotExpandedDict(self.data).with_lists().get('settings', {})
        settings = list(zip(raw_settings.get('technique', []), raw_settings.get('value', [])))
        data['settings'] = {int(k): v for k, v in settings if v}
        data['start_date'] = data['cycle'].start_date
        return data


class ReviewCycleForm(forms.ModelForm):
    class Meta:
        model = models.ReviewCycle
        fields = ('start_date', 'open_date', 'close_date', 'end_date', 'due_date', 'alloc_date')

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "review-cycle-form"
        self.helper.form_action = self.request.get_full_path()
        self.helper.title = "Configure Review Cycle"

        self.helper.layout = Layout(
            Div(
                Div(DateField("start_date"), css_class="col-sm-6"),
                Div(DateField("end_date"), css_class="col-sm-6"),
                Div(DateField("open_date"), css_class="col-sm-6"),
                Div(DateField("close_date"), css_class="col-sm-6"),
                Div(DateField("due_date"), css_class="col-sm-6"),
                Div(DateField("alloc_date"), css_class="col-sm-6"),
                css_class="row narrow-gutter"
            ),
            Div(
                Div(
                    Div(
                        StrictButton('Revert', type='reset', value='Reset', css_class="btn btn-default"),
                        StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            )
        )


class ReviewTrackForm(forms.ModelForm):
    committee = forms.ModelMultipleChoiceField(queryset=models.Reviewer.objects.all(), required=False)

    class Meta:
        model = models.ReviewTrack
        fields = ('name', 'acronym', 'description',
                  'min_reviewers', 'max_proposals', 'committee')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, }),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "review-track-form"
        self.helper.form_action = self.request.get_full_path()
        self.helper.title = "Edit Review Track Information"

        self.helper.layout = Layout(
            Div(
                Div("name", css_class="col-sm-8"),
                Div("acronym", css_class="col-sm-4"),
                Div("description", css_class="col-sm-12"),
                Div("min_reviewers", css_class="col-sm-6"),
                Div("max_proposals", css_class="col-sm-6"),
                Div(Field("committee", css_class="chosen"), css_class="col-sm-12"),
                css_class="row narrow-gutter"
            ),
            Div(
                Div(
                    Div(
                        StrictButton('Revert', type='reset', value='Reset', css_class="btn btn-default"),
                        StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
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
                css_class="row narrow-gutter"
            ),
            Div(
                Div(
                    Div(
                        StrictButton('Revert', type='reset', value='Reset', css_class="btn btn-default"),
                        StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            )
        )


class ReviewerAssignmentForm(forms.ModelForm):
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

        self.helper.title = "Edit Reviewer Assignment"
        self.helper.form_action = self.request.get_full_path()

        cycle = self.instance.cycle
        track = self.instance.track

        prop_info = utils.get_submission_info(self.instance)

        tech_filter = Q(techniques__in=prop_info['techniques'])
        area_filter = Q(areas__in=prop_info['areas'])

        reviewers = cycle.reviewers.filter(tech_filter, area_filter, Q(committee__isnull=True))
        reviewers = reviewers.distinct().annotate(
            num_reviews=Sum(
                Case(
                    When(Q(user__reviews__cycle=cycle), then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ),
        )

        if track.max_proposals > 0:
            reviewers = reviewers.exclude(num_reviews__gt=track.max_proposals)

        valid = [
            rev.pk for rev in reviewers.all()
            if not utils.veto_conflict(prop_info, utils.get_reviewer_info(rev))
        ] + [
            rev.pk for rev in track.committee.all()
            if not utils.veto_conflict(prop_info, utils.get_reviewer_info(rev))
        ]
        reviewers = models.Reviewer.objects.filter(Q(pk__in=valid)).order_by('committee')

        self.fields['reviewers'].queryset = reviewers.distinct()
        self.helper.title = 'Add Reviewers'
        self.helper.layout = Layout(
            Div(
                HTML("{% include 'proposals/submission-snippet.html' with submission=form.instance %}"),
                css_class=""
            ),
            Div(
                Div(Field('reviewers', css_class="chosen"), css_class='col-sm-12'),
                css_class="row narrow-gutter"
            ),
            Div(
                Div(
                    Div(
                        StrictButton('Revert', type='reset', value='Reset', css_class="btn btn-default"),
                        StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
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
                Div(Field('value', css_class="chosen"), css_class="col-sm-12"),
                Div("reason", css_class="col-sm-12"),
                css_class="row narrow-gutter"
            ),
            Div(
                Div(
                    StrictButton('Delete', id="delete-object", css_class="btn btn-danger pull-left",
                                 data_url=delete_url),
                    StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary pull-right'),
                    StrictButton('Cancel', type='button', data_dismiss='modal', css_class="btn btn-default pull-right"),

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
                css_class="row narrow-gutter"
            ),
            Div(
                Div(
                    Div(
                        StrictButton('Cancel', type='button', data_dismiss='modal', css_class="btn btn-default"),
                        StrictButton('Save', type='submit', value='Save', css_class='btn btn-primary'),
                        css_class='pull-right'
                    ),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            ),
        )
