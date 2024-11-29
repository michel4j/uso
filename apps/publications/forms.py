

from datetime import datetime, date
from crispy_forms.bootstrap import AppendedText, AccordionGroup, Accordion
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Div, Field, HTML, Button
from crispy_forms.bootstrap import FieldWithButtons, StrictButton, FormActions
from django.urls import reverse_lazy
from django import forms
from django.db.models import Q
from django.utils.translation import gettext as _
from django.utils.safestring import mark_safe
from . import models
from .models import Publication, Facility, Journal, FundingSource
from model_utils import Choices
import json
from . import utils

PUBLICATION_FIELDS = ['title', 'authors', 'kind', 'tags', 'users', 'areas', 'date',
                      'funders', 'notes', 'keywords', 'beamlines', 'reviewed']
PUBLICATION_WIDGETS = {
    'title': forms.Textarea(attrs={'rows': 2}),
    'authors': forms.Textarea(attrs={'rows': 2}),
    'editor': forms.TextInput(),
    'notes': forms.Textarea(attrs={'rows': 1}),
    'keywords': forms.Textarea(attrs={'rows': 2}),
    'reviewed': forms.HiddenInput(),
}


def json_default(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime) or isinstance(obj, date):
        serial = obj.isoformat()
        return serial
    raise TypeError("Type not serializable")


class PublicationReviewForm(forms.ModelForm):
    class Meta:
        model = models.Publication
        fields = PUBLICATION_FIELDS
        widgets = PUBLICATION_WIDGETS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        # self.fields['funders'].queryset = models.FundingSource.objects.filter(Q(location__icontains='Canada'))
        self.fields['reviewed'].initial = True
        self.fields['users'].help_text = ""
        self.fields[
            'funders'].help_text = "Start typing names or acronyms of funding agencies acknowledged in this paper."
        self.fields['funders'].queryset = models.FundingSource.objects.filter(location__icontains='Canada')
        self.fields['beamlines'].help_text = ""
        self.helper.layout = Layout(
            Fieldset(_("Review Publication Details"),
                     Div(
                         Div(
                             Div(HTML("""{{object.cite|safe}}"""), css_class="tinytron"), css_class="col-sm-12"),
                         css_class="row narrow-gutter"
                     ),

                     Accordion(
                         AccordionGroup("Details",
                                        Div(
                                            Div(Field('kind', css_class="chosen"), css_class='col-sm-12'),
                                            Div('title', css_class='col-sm-12'),
                                            Div('authors', css_class='col-sm-12'),
                                            Div(AppendedText("date", mark_safe('<i class="bi-calendar"></i>')),
                                                css_class="col-sm-12"),
                                            css_class="row narrow-gutter",
                                        ),
                                        self._extra_fields(),
                                        active=False
                                        )
                     ),
                     Accordion(
                         AccordionGroup("Additional Information",
                                        Div(
                                            Div(Field('tags', css_class="chosen", placeholder="select all that apply"),
                                                css_class='col-sm-6'),
                                            Div(Field('areas', css_class="chosen", placeholder="select all that apply"),
                                                css_class='col-sm-6'),
                                            Div(Field('beamlines', css_class="chosen"), css_class='col-sm-6'),
                                            Div(Field('users', css_class="chosen"), css_class='col-sm-6'),
                                            Div(Field('funders', css_class="chosen",
                                                      placeholder="select funding sources"),
                                                css_class='col-sm-12'),
                                            Div('keywords', css_class='col-sm-12'),
                                            Div('notes', css_class='col-sm-12'),
                                            css_class="row narrow-gutter"
                                        ),
                                        ),
                     )
                     ),
            FormActions(
                StrictButton('Delete', id="delete-object",
                             css_class="btn btn-danger",
                             data_url=f"{reverse_lazy('delete-publication', kwargs={'pk': self.instance.pk})}"),
                Div(
                    StrictButton('Revert', type='reset', value='Reset', css_class="btn btn-default"),
                    StrictButton('Reviewed', type='submit', value='Submit', css_class='btn btn-primary'),
                    css_class='pull-right'),
            )
        )

    def clean(self):
        data = super().clean()
        bls = {bl for bl in data['beamlines'] if not bl.kind == bl.TYPES.sector}
        for bl in [x for x in data['beamlines'] if (x.kind == x.TYPES.sector)]:
            bls.update(bl.units.all())
        data['beamlines'] = bls
        data['reviewed'] = True
        return data

    def _extra_fields(self):
        return Div()


class ArticleReviewForm(PublicationReviewForm):
    class Meta:
        model = models.Article
        fields = PUBLICATION_FIELDS + ['code', 'journal', 'volume', 'number', 'pages']
        widgets = PUBLICATION_WIDGETS

    def _extra_fields(self):
        self.fields['code'].widget.attrs['readonly'] = True
        return Div(Div(Field('journal', css_class="chosen"), css_class='col-sm-4'),
                   Div('volume', css_class='col-sm-1'),
                   Div("number", css_class='col-sm-1'),
                   Div("pages", css_class='col-sm-2'),
                   Div("code", css_class='col-sm-4'),
                   css_class="row narrow-gutter"
                   )


class BookReviewForm(PublicationReviewForm):
    class Meta:
        model = models.Book
        fields = PUBLICATION_FIELDS + ['code', 'main_title', 'editor', 'publisher', 'edition', 'address', 'volume',
                                       'edition', 'pages']
        widgets = PUBLICATION_WIDGETS

    def _extra_fields(self):
        if 'thesis' in self.initial['kind']:
            self.fields['code'].label = "ISBN, DOI, or URL"
            for fld in ['main_title', 'volume', 'edition', 'pages']:
                self.fields[fld].widget = forms.HiddenInput()
            self.fields['editor'].label = 'Supervisor(s)'
            self.fields['publisher'].label = 'University'
            self.fields['address'].label = 'Location, Country'

            return Div(
                Div("code", css_class='col-sm-6'),
                Div('editor', css_class='col-sm-6'),
                Div('publisher', css_class='col-sm-6'),
                Div('address', css_class='col-sm-6'),
                css_class="row narrow-gutter"
            )
        else:
            return Div(
                Div('main_title', css_class='col-sm-4'),
                Div('volume', css_class='col-sm-1'),
                Div("edition", css_class='col-sm-2'),
                Div("pages", css_class='col-sm-2'),
                Div("code", css_class='col-sm-3'),
                Div('editor', css_class='col-sm-4'),
                Div('publisher', css_class='col-sm-4'),
                Div('address', css_class='col-sm-4'),
                css_class="row narrow-gutter"
            )


class PDBReviewForm(PublicationReviewForm):
    class Meta:
        model = models.PDBDeposition
        fields = PUBLICATION_FIELDS + ['code', 'reference']
        widgets = PUBLICATION_WIDGETS

    def _extra_fields(self):
        self.fields['code'].widget.attrs['readonly'] = True
        self.fields['kind'].widget.attrs['readonly'] = True
        self.fields['reference'].queryset = models.Article.objects.all()
        self.fields['reference'].required = False
        return Div(
            Div('code', css_class='col-sm-2'),
            Div(Field('reference', css_class="chosen"), css_class='col-sm-10'),
            css_class="row narrow-gutter"
        )


REFERENCE_FETCH = {
    'doi': utils.get_pub,
    'isbn': utils.get_book,
    'patent': utils.get_patent,
    'url': utils.get_thesis,
}


class PubWizardForm1(forms.Form):
    REFERENCES = [("doi", "DOI"),
                  ("isbn", "ISBN"),
                  ("patent", "Patent Number"),
                  ("url", "Thesis")]
    reference = forms.ChoiceField(
        choices=REFERENCES,
        required=False,
        label="What kind of reference do you have for the publication?",
        help_text="peer-reviewed article or conference proceedings"
    )
    code = forms.CharField(required=False, label=" ")
    details = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "modal-form"
        self.helper.form_action = reverse_lazy("add-publication")
        self.helper.title = "Report a Publication"
        self.helper.layout = Layout(

            Div(
                Div(Field('reference', css_class="chosen"), css_class="col-sm-12 modal-update"),
                Div('code', css_class="col-sm-12"),
                css_class="row"
            ),
            Div(
                Div(
                    StrictButton('Cancel', value="Cancel", data_dismiss="modal", css_class='btn-default pull-left'),
                    StrictButton('Continue', type="submit", value="Submit", css_class='btn-primary pull-right'),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            ),
            'details',
        )

    def clean(self):
        super().clean()
        data = self.cleaned_data
        reference = data.get("reference")
        code = data.get("code")
        if not code:
            raise forms.ValidationError(_('Provide a reference for the publication'),
                                        code='reference-required',
                                        params={'reference': reference})
        elif reference in ['doi', 'isbn', 'patent', 'url']:
            details = REFERENCE_FETCH[reference](code)
            if not details:
                raise forms.ValidationError(
                    _('Unable to find %(reference)s with that reference'),
                    code='not-found',
                    params={'reference': reference})
            else:
                data['details'] = json.dumps(details, default=json_default)
        return data


class PubWizardForm2(forms.Form):
    details = forms.CharField(required=False, widget=forms.HiddenInput)
    title = forms.CharField(max_length=255, required=False)
    authors = forms.CharField(max_length=255, required=False)
    date = forms.DateField(label=_('Date Published'), required=False)
    keywords = forms.CharField(max_length=500, required=False)
    kind = forms.ChoiceField(choices=Publication.TYPES, required=False)
    code = forms.CharField(label=_("URL"), required=False)

    main_title = forms.CharField(max_length=255, required=False)
    editor = forms.CharField(max_length=255, required=False)
    publisher = forms.CharField(max_length=100, required=False)
    address = forms.CharField(label=_('Location (Province, Country)'), max_length=50, required=False)
    edition = forms.CharField(max_length=10, required=False)
    volume = forms.CharField(max_length=10, required=False)
    pages = forms.CharField(max_length=20, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = "modal-form"
        self.helper.form_action = reverse_lazy("add-publication")
        self.helper.title = "Report a Publication"

        self.autobuttons = FormActions(
            StrictButton('Cancel', value="Cancel", data_dismiss="modal", css_class='btn-default pull-left'),
            StrictButton('No, Start Over', type="submit", name="wizard_goto_step", value="0",
                         css_class='btn-danger pull-left'),
            StrictButton('Yes, Continue', type="submit", value="Submit", css_class='btn-primary pull-right'),
            css_class="col-xs-12"
        )
        self.buttons = FormActions(
            StrictButton('Cancel', value="Cancel", data_dismiss="modal", css_class='btn-default pull-left'),
            StrictButton('Start Over', type="submit", name="wizard_goto_step", value="0",
                         css_class='btn-danger pull-left'),
            StrictButton('Continue', type="submit", value="Submit", css_class='btn-primary pull-right'),
            css_class="col-xs-12"
        )

    def update_helper(self):

        try:
            details = json.loads(self.initial.get('details', ""))
        except:
            details = {}
        kind = details.get('kind', None)

        for f in list(self.fields.keys()):
            if details.get(f, None):
                self.initial[f] = details[f]
                if kind and 'thesis' not in kind:
                    self.fields[f].widget = forms.HiddenInput()

        if kind and 'thesis' not in kind:
            template_name = 'default'
            if kind in models.Article.TYPES:
                name = self.initial.get('kind', 'article')
                template_name = name
                code = "DOI"
                extras = Div()
            elif kind in models.Book.TYPES:
                name = self.initial.get('kind', 'chapter')
                template_name = 'book'
                code = "Reference Code"
                extras = Div(
                    Div('main_title', css_class="col-sm-12"),
                    Div('editor', css_class="col-sm-12"),
                    Div('publisher', css_class="col-sm-6"), Div('address', css_class="col-sm-6"),
                    Div('title', css_class="col-sm-12"),
                    Div('authors', css_class="col-sm-12", placeholder="Separate with a semicolon"),
                    Div('edition', css_class="col-sm-4"), Div('volume', css_class="col-sm-4"),
                    Div('pages', css_class="col-sm-4"),
                    Div(AppendedText("date", mark_safe('<i class="bi-calendar"></i>')), css_class="col-sm-12"),
                    Div(Field('keywords', placeholder="Separate with a semicolon"), css_class="col-sm-12"),
                    css_class="row narrow-gutter"
                )
                for k in ['edition', 'volume', 'pages']:
                    if self.initial.get(k, None):
                        for k in ['edition', 'volume', 'pages']:
                            self.fields[k].widget = forms.HiddenInput()
                        break
                if self.initial.get('publisher', None):
                    self.fields['publisher'].widget = forms.HiddenInput()
                    self.fields['address'].widget = forms.HiddenInput()

                self.fields["authors"].label = "Authors (if different than the book editors)"
                self.fields["title"].label = "Chapter/Section Title (if applicable)"

            elif kind in models.Patent.TYPES:
                name = self.initial.get('kind', 'patent')
                template_name = name
                code = "Patent Number"
                extras = Div(
                    Div("title", css_class="col-sm-12"),
                    Div("authors", css_class="col-sm-12", placeholder="Separate with a semicolon"),
                    Div(AppendedText("date", mark_safe('<i class="bi-calendar"></i>')), css_class="col-sm-12"),
                    Div(Field('keywords', placeholder="Separate with a semicolon"), css_class="col-sm-12"),
                    css_class="row narrow-gutter"
                )
            type_name = dict(Publication.TYPES)[name]
            self.helper.title = "Is this the right {type_name}?".format(type_name=type_name)
            reference = Div(
                HTML("""<label class="control-label">{type_name}:</label>
                    <div class="highlight">{{% load pubstats %}}
                      {{% autoescape off %}}
                        {{{{ "{template_name}"|get_citation:form.initial.details}}}}
                      {{% endautoescape %}}
                    </div>""".format(type_name=type_name.title(), template_name=template_name)),
                HTML(details.get('code', None) and """<label class="control-label">{code_name}:</label>
                    <div class="highlight">{code}</div>""".format(code_name=code, code=details.get('code', '')) or ""),
                HTML(self.initial.get('keywords', None) and """<label class="control-label">Keywords:</label>
                    <div class="highlight">{{ form.initial.keywords }}</div><br>""" or "")
            )
            self.helper.layout = Layout(
                Accordion(
                    AccordionGroup("Details",
                                   reference,
                                   active=True
                                   ),
                ),
                extras, 'details', 'kind',
                Div(self.autobuttons, css_class="modal-footer row")
            )
        else:
            self.fields["authors"].label = _("Author")
            self.fields["publisher"].label = _("University/Institution")
            self.fields["editor"].label = _("Supervisor(s)")
            self.fields["kind"].choices = Choices(
                ('msc_thesis', _('Masters Thesis')),
                ('phd_thesis', _('Doctoral Thesis')))
            self.helper.title = "Tell us more about the thesis"
            self.helper.layout = Layout(
                Div(
                    Div("title", css_class="col-sm-12"),
                    Div("authors", css_class="col-sm-6", placeholder="Separate with a semicolon"),
                    Div(Field('editor', placeholder="Last, First; Last, F.; etc ..."), css_class="col-sm-6"),

                    Div("publisher", css_class="col-sm-6"), Div("address", css_class="col-sm-6"),
                    Div(Field("kind", css_class="chosen"), css_class="col-sm-6"),
                    Div(AppendedText("date", mark_safe('<i class="bi-calendar"></i>')), css_class="col-sm-6"),
                    Div(Field("code", placeholder="Handle link or other link to thesis if available"),
                        css_class="col-sm-12"),
                    Div(Field('keywords', placeholder="Separate with a semicolon"), css_class="col-sm-12"),
                    css_class="row narrow-gutter"
                ),

                Div(self.buttons, css_class="modal-footer row")
            )


class PubWizardForm3(forms.Form):
    details = forms.CharField(required=False, widget=forms.HiddenInput, initial="{}")
    obj = forms.ModelChoiceField(queryset=Publication.objects.all().select_subclasses(), widget=forms.HiddenInput,
                                 required=False)

    beamlines = forms.ModelMultipleChoiceField(queryset=Facility.objects.all(), required=False)
    funders = forms.ModelMultipleChoiceField(queryset=FundingSource.objects.all(), required=False)
    author = forms.BooleanField(required=False, label="I am an author on this paper", widget=forms.CheckboxInput)
    notes = forms.CharField(max_length=512, required=False, widget=forms.Textarea,
                            label=_(
                                "Are there any corrections to the citation details, or extra information about this publication that is of interest?"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = "modal-form"
        self.helper.form_action = reverse_lazy("add-publication")
        self.helper.title = "Provide some extra information"
        self.fields[
            'beamlines'].help_text = "Select the CLS beamline(s) used to collect data for this research, if applicable."
        self.fields['funders'].help_text = "Select any funding sources contributing to this research."
        self.fields['funders'].queryset = FundingSource.objects.filter(
            location__in=['Canada', 'United States']).order_by('location', 'name')

        self.cls_details = AccordionGroup(
            "CLS and Funding Information",
            Div(
                Div(Field('beamlines', placeholder="Start typing a beamline name", css_class="chosen"),
                    css_class='col-sm-6'),
                Div(Field('funders', placeholder="Start typing a funding source", css_class="chosen"),
                    css_class='col-sm-6'),
                Div('author', css_class="col-sm-12"),
                css_class="row narrow-gutter",
            ),
            active=True,
        )
        self.extra_notes = AccordionGroup(
            "Additional Notes",
            Field('notes'),
            active=False,
        )
        self.helper.layout = Layout()

    def update_helper(self):

        try:
            details = json.loads(self.initial.get('details', ""))
        except:
            details = {}
        kind = details.get('kind', None)

        if self.initial.get('obj', None):
            warning = HTML("<div class='alert alert-info'>"
                           "<h4>Is this the same publication?</h4>"
                           "<small>{{ form.initial.obj.cite|safe }}</small>"
                           "<p class='help-block'>If not, please continue. "
                           "Otherwise, start over to enter another publication.</p></div>")
        else:
            warning = HTML("")

        template_name = 'default'
        if kind:
            if kind in models.Article.TYPES:
                name = self.initial.get('kind', 'article')
                template_name = name
            elif kind in models.Book.TYPES:
                name = self.initial.get('kind', 'chapter')
                template_name = 'book'
            elif kind in models.Patent.TYPES:
                name = self.initial.get('kind', 'patent')
                template_name = 'patent'
        else:
            name = self.initial.get('kind', 'thesis')
            template_name = (name == 'thesis' and 'book') or 'default'

        type_name = dict(Publication.TYPES).get(name, 'Publication')
        reference = Div(
            HTML("""<label class="control-label">{type_name}:</label>
                <div class="highlight">{{% load pubstats %}}
                  {{% autoescape off %}}
                    {{{{ "{template_name}"|get_citation:form.initial.details}}}}
                  {{% endautoescape %}}
                </div>""".format(type_name=type_name, template_name=template_name)),
            HTML(details.get('keywords', None) and """<label class="control-label">Keywords:</label>
                <div class="highlight">{keywords}</div><br>""".format(keywords=details['keywords']) or ""),
            'obj', 'details'
        )

        self.helper.layout = Layout(
            Div(
                Div(
                    warning,
                    css_class="col-xs-12"
                ),
                css_class="row"
            ),
            Accordion(
                AccordionGroup("Review the Details",
                               reference,
                               active=False,
                               ),
                self.cls_details,
                self.extra_notes
            ),
            Div(
                FormActions(
                    StrictButton('Cancel', value="Cancel", data_dismiss="modal", css_class='btn-default pull-left'),
                    StrictButton('Start Over', type="submit", name="wizard_goto_step", value="0",
                                 css_class='btn-danger pull-left'),
                    StrictButton('Submit', type="submit", value="Submit", css_class='btn-primary pull-right'),
                    css_class="col-xs-12"
                ),
                css_class="modal-footer row"
            )
        )
