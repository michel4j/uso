from crisp_modals.forms import ModalModelForm, FullWidth, Row, ThirdWidth, TwoThirdWidth
from crispy_forms.bootstrap import StrictButton
from crispy_forms.layout import Layout, Div, HTML, Field
from django import forms
from django.apps import apps
from django.db import models, ProgrammingError
from django.core.exceptions import ValidationError

from .models import Clarification, Attachment


class Fieldset(Div):
    def __init__(self, title, *args, **kwargs):
        if 'css_class' not in kwargs:
            kwargs['css_class'] = "row"
        super().__init__(
            Div(HTML("<h3>{}</h3><hr class='hr-xs'/>".format(title)), css_class="col-sm-12"),
            *args,
            **kwargs
        )


class ClarificationForm(ModalModelForm):
    class Meta:
        model = Clarification
        fields = ['requester', 'question', 'content_type', 'object_id']
        widgets = {
            'requester': forms.HiddenInput(),
            'object_id': forms.HiddenInput(),
            'content_type': forms.HiddenInput(),
            'question': forms.Textarea(attrs={'rows': 5})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.body.append(
            Row(
                FullWidth('question'),
                Field('requester'),
                Field('content_type'),
                Field('object_id'),
            ),
        )


class ResponseForm(ModalModelForm):
    class Meta:
        model = Clarification
        fields = ['response', 'responder']
        widgets = {
            'response': forms.Textarea(attrs={'rows': 5}),
            'responder': forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.body.append(
            Row(
                Div(
                    HTML(
                        f'<h4>{self.instance.reference}</h4><hr/><span>{self.instance.question}</span>'
                    ),
                    css_class="alert alert-info"
                ),
                FullWidth('response'),
            ),
            Field('responder'),
        )


class AttachmentForm(ModalModelForm):
    class Meta:
        model = Attachment
        fields = ('owner', 'content_type', 'object_id', 'file', 'description', 'kind')
        widgets = {
            'content_type': forms.HiddenInput,
            'object_id': forms.HiddenInput,
            'owner': forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.body.title = "Manage Attachments"
        self.body.append(
            Row(
                ThirdWidth('kind'),
                TwoThirdWidth('description'),
                FullWidth(Field('file', template="%s/file_input.html")),
                Field('owner'), Field('object_id'), Field('content_type'),
            ),
        )
        self.footer.layout = Layout(
            StrictButton('Close', css_class='btn btn-secondary', data_bs_dismiss="modal", aria_label="Close")
        )


class JSONDictionaryWidget(forms.MultiWidget):
    """
    A widget that displays a JSON dictionary of string:float as a list of
    key-value input pairs.
    """
    template_name = 'misc/widgets/json-dict.html'

    def __init__(self, attrs=None, max_pairs=5):
        self.max_pairs = max_pairs
        # Create a list of widgets for each key-value pair.
        # Each pair consists of a TextInput for the key and a NumberInput for the value.
        widgets = []
        for i in range(self.max_pairs):
            widgets.append(forms.TextInput(attrs={'placeholder': 'Field name'}))
            widgets.append(forms.NumberInput(attrs={'placeholder': 'Weight', 'step': '0.01'}))
        super().__init__(widgets, attrs)

    def decompress(self, value):
        """
        Takes a single dictionary value from the database and splits it
        into a list of values for the individual widgets.

        :param value: A python dictionary (or None).
        :return: A list of values for the text/number inputs.
        """

        if isinstance(value, dict):
            # Pad the dictionary with empty items to ensure we have enough
            # items to match the number of widgets.
            items = list(value.items())
            while len(items) < self.max_pairs:
                items.append(('', ''))

            # Flatten the list of (key, value) tuples
            return [item for pair in items for item in pair]

        # If there's no value, return a list of empty strings for all widgets.
        return ['' for _ in range(self.max_pairs * 2)]

    def get_context(self, name, value, attrs):
        """
        Overrides the default get_context to group the widgets into pairs,
        """
        context = super().get_context(name, value, attrs)

        # Replace the subwidgets with our grouped pairs
        subwidgets = context['widget']['subwidgets']
        context['widget']['subwidgets'] = [
            {
                'key': key_widget,
                'value': value_widget
            }
            for key_widget, value_widget in zip(subwidgets[::2], subwidgets[1::2])
        ]
        return context


class JSONDictionaryField(forms.MultiValueField):
    """
    A field that represents a dictionary of string:float.
    It uses the JSONDictionaryWidget for rendering.
    """

    def __init__(self, **kwargs):
        max_pairs = kwargs.pop('max_pairs', 5)

        # Define a CharField and a FloatField for each pair.
        fields = []
        for i in range(max_pairs):
            fields.append(forms.CharField(required=False))
            fields.append(forms.FloatField(required=False))

        super().__init__(
            fields=tuple(fields),
            widget=JSONDictionaryWidget(max_pairs=max_pairs),
            require_all_fields=False,
            **kwargs
        )

    def compress(self, data_list):
        """
        Takes the list of cleaned values from the form's fields and
        "compresses" them back into a single Python dictionary.

        :param data_list: A list of cleaned data, e.g., ['a', 1.0, 'b', 2.0, '', None, ...]
        :return: A dictionary of key:value pairs.
        """
        if not data_list:
            return {}

        dictionary = {}
        # Iterate through the list in chunks of 2 (key, value).
        for i in range(0, len(data_list), 2):
            key = data_list[i]
            value = data_list[i + 1]

            # Only include pairs where the key is provided.
            if key and value is not None:
                # Basic validation: ensure keys are unique.
                if key in dictionary:
                    raise ValidationError(f"Duplicate key found: '{key}'. Keys must be unique.")
                dictionary[key] = value

        return dictionary


class ModelPoolWidget(forms.MultiWidget):
    """
    A widget that displays an float input for model items and allows allocation
    of percentage weights to each item with auto-update.
    """
    template_name = 'misc/widgets/pools.html'

    def __init__(self, model, attrs=None):
        # Create a list of widgets for each key-value pair.
        # Each pair consists of a TextInput for the key and a NumberInput for the value.
        attrs = attrs or {}
        self.model = model
        if apps.ready:
            try:
                self.entries = self.model.objects.in_bulk()
            except ProgrammingError as e:
                # If the model does not exist or has no entries, we can still create the widget.
                # This is useful for cases where the model might not be ready yet
                self.entries = {}
            self.names = [str(item) for item in self.entries.values()]
            self.items = list(self.entries.values())
            widgets = []
            for item in self.items:
                item_attrs = {**attrs}
                if item.is_default:
                    item_attrs['readonly'] = True
                widgets.append(
                    forms.TextInput(attrs=item_attrs)
                )
            super().__init__(widgets, attrs)

    def decompress(self, value):
        """
        Takes a single dictionary value from the database and splits it
        into a list of values for the individual widgets.

        :param value: A python dictionary (or None).
        :return: A list of values for the text/number inputs.
        """
        if isinstance(value, dict):
            # Pad the dictionary with empty items to ensure we have enough
            # items to match the number of widgets.

            return [
                value.get(pk, value.get(str(pk), ''))
                for pk in self.entries.keys()
            ]

        # If there's no value, return a list of empty strings for all widgets.
        return ['' * len(self.entries)]

    def get_context(self, name, value, attrs):
        """
        Overrides the default get_context to group the widgets into pairs,
        """
        context = super().get_context(name, value, attrs)

        # Replace the subwidgets with our grouped pairs
        subwidgets = context['widget']['subwidgets']
        context['widget']['subwidgets'] = [
            (name, widget, item)
            for name, widget, item in zip(self.names, subwidgets, self.items)
        ]
        return context


class ModelPoolField(forms.MultiValueField):
    """
    A widget that displays an float input for model items and allows allocation
    of percentage weights to each item with auto-update.
    """

    def __init__(self, **kwargs):
        model = kwargs.pop('model', None)

        if apps.ready:
            if isinstance(model, str):
                # If a string is provided, assume it's a model name and import it.
                model = apps.get_model(model)

            elif not model or not issubclass(model, models.Model):
                raise ValueError("ModelPoolField requires a valid Django model.")

            # Define a FloatField for each pair.
            fields = []
            try:
                self.entries = model.objects.in_bulk()
                for name, item in self.entries.items():
                    fields.append(forms.IntegerField(required=False))
            except ProgrammingError as e:
                # If the model does not exist or has no entries, we can still create the field.
                # This is useful for cases where the model might not be ready yet
                pass

            super().__init__(
                fields=tuple(fields),
                widget=ModelPoolWidget(model),
                require_all_fields=False,
                **kwargs
            )

    def compress(self, data_list):
        """
        Takes the list of cleaned values from the form's fields and
        "compresses" them back into a single Python dictionary.

        :param data_list: A list of cleaned data, e.g., ['a', 1.0, 'b', 2.0, '', None, ...]
        :return: A dictionary of key:value pairs.
        """
        if not data_list:
            return {}

        dictionary = {}
        # Iterate through the list
        for i, pk in enumerate(self.entries.keys()):
            # Get the value for this key
            value = data_list[i]
            if value not in (None, '', ' '):
                if isinstance(value, str):
                    value = value.strip()
                dictionary[pk] = value

        return dictionary



