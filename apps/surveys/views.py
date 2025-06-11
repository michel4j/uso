
import collections

from django.conf import settings
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.views.generic import detail

from . import forms
from dynforms.models import FormType
from dynforms.views import DynCreateView
from projects.models import Project
from proposals.models import ReviewCycle
from roleperms.views import RolePermsViewMixin
from .models import Feedback

USO_ADMIN_ROLES = getattr(settings, "USO_ADMIN_ROLES", ["admin:uso"])


class UserFeedback(DynCreateView):
    form_class = forms.FeedbackForm
    model = Feedback
    template_name = "projects/forms/project_form.html"

    def get_initial(self):
        initial = super().get_initial()
        return initial

    def get_form_type(self) -> FormType:
        form_type = FormType.objects.get(name="feedback")
        return form_type

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = "User Feedback"
        return context

    def get_success_url(self):
        success_url = reverse("user-dashboard")
        return success_url

    def form_valid(self, form):
        data = form.cleaned_data
        obj = self.model(**data)
        obj.save()
        return HttpResponseRedirect(self.get_success_url())


class ReviewCycleFeedback(RolePermsViewMixin, detail.DetailView):
    template_name = "proposals/cycle-feedback.html"
    model = ReviewCycle
    admin_roles = USO_ADMIN_ROLES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        surveys = self.object.feedback.all()
        specs = set(surveys.values_list('spec_id', flat=True).distinct())
        beamlines = surveys.values_list('beamline__acronym', flat=True).distinct()
        context['specs'] = []
        for spk in specs:
            feedback = surveys.filter(spec_id=spk)
            data = {}
            form_type = FormType.objects.get(pk=spk)
            for p in form_type.pages:
                data[p['name']] = collections.OrderedDict({})
                fields = {f['name']: f for f in p['fields']}
                for f, d in list(fields.items()):
                    if 'comments' in f and f.replace('_comments', '') in list(fields.keys()):
                        continue
                    if d['field_type'] in ['multiplechoice', 'checkboxes']:
                        choices = d.get('choices')
                        if d['field_type'] == 'multiplechoice':
                            results = [fbk.details.get(f) for fbk in feedback if fbk.details.get(f)]
                            blresults = {bl: [fbk.details.get(f) for fbk in feedback.filter(beamline__acronym=bl) if
                                              fbk.details.get(f)] for bl in beamlines}
                            if any(['(' in choice for choice in choices]) and not any(
                                    [choice in set(results) for choice in choices]):
                                choices = [choice.split('(')[0].strip() for choice in d.get('choices')]
                            d['responses'] = len(results)
                        else:
                            results = [fbk.details.get(f).split(';') for fbk in feedback if fbk.details.get(f)]
                            blresults = {bl: [item for sublist in [fbk.details.get(f).split(';') for fbk in
                                                                   feedback.filter(beamline__acronym=bl) if
                                                                   fbk.details.get(f)] for item in sublist] for bl in
                                         beamlines}
                            d['responses'] = len(results)
                            results = [item.strip() for sublist in results for item in sublist if item.strip()]
                        if d['responses']:
                            d['results'] = [{'Total': [
                                {'x': str(i), 'y': results.count(i) / float(d['responses']), 'val': results.count(i)}
                                for i in choices]}]
                            d['results'] += [{str(bl): [{'x': str(i), 'val': blresults[bl].count(i)} for i in choices]}
                                             for bl in beamlines]
                            d['chart'] = [[str(bl), [blresults[bl].count(i) for i in choices]] for bl in beamlines]
                            d['chart'].append(['Total', [results.count(i) for i in choices]])
                        else:
                            d['results'] = [
                                {'Total': [{'x': str(i), 'y': 0, 'val': results.count(i)} for i in choices]}]
                        d['options'] = choices
                        if '{0}_comments'.format(f) in list(fields.keys()):
                            d['comments'] = [(fbk, fbk.details.get('{0}_comments'.format(f)), fbk.details.get(f)) for
                                             fbk in feedback if fbk.details.get('{0}_comments'.format(f))]
                    else:
                        d['results'] = [(fbk, fbk.details.get(f)) for fbk in feedback if fbk.details.get(f)]
                        d['responses'] = len(d['results'])
                    data[p['name']][f] = d
                data[p['name']] = collections.OrderedDict(sorted(data[p['name']].items()))
            context['specs'].append({
                'pages': collections.OrderedDict(sorted(data.items())),
                'responses': feedback.count(),
                'spec': spk
            })
            context['responses'] = surveys.count()
        return context
