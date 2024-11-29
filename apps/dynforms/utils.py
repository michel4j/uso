
import itertools
import operator
import urllib.request, urllib.parse, urllib.error
from collections.abc import MutableMapping
from django.urls import reverse
from django.db.models import Q

FIELD_SEPARATOR = '__'


def _toInt(val, default=None):
    try:
        return int(val)
    except ValueError:
        return default


def dict_list(d):
    if not isinstance(d, dict):
        return d
    else:
        keys = {k: _toInt(k) for k in list(d.keys())}
        if all([isinstance(v, int) for k, v in list(keys.items())]):
            return [
                dict_list(pair[1])
                for pair in sorted([(keys[k], d[k]) for k in list(d.keys())])
            ]
        else:
            return {k: dict_list(v) for k, v in list(d.items())}


class DotExpandedDict(dict):
    """
    A special dictionary constructor that takes a dictionary in which the keys
    may contain dots to specify inner dictionaries. It's confusing, but this
    example should make sense.

    >>> d = DotExpandedDict({'person.1.firstname': ['Simon'], \
    'person.1.lastname': ['Willison'], \
    'person.2.firstname': ['Adrian'], \
    'person.2.lastname': ['Holovaty']})
    >>> d
    {'person': {'1': {'lastname': ['Willison'], 'firstname': ['Simon']}, '2': {'lastname': ['Holovaty'], 'firstname': ['Adrian']}}}
    >>> d['person']
    {'1': {'lastname': ['Willison'], 'firstname': ['Simon']}, '2': {'lastname': ['Holovaty'], 'firstname': ['Adrian']}}
    >>> d['person']['1']
    {'lastname': ['Willison'], 'firstname': ['Simon']}

    # Gotcha: Results are unpredictable if the dots are "uneven":
    >>> DotExpandedDict({'c.1': 2, 'c.2': 3, 'c': 1})
    {'c': 1}
    """

    def __init__(self, key_to_list_mapping):
        super().__init__()
        for k, v in list(key_to_list_mapping.items()):
            current = self
            bits = k.split('.')
            for bit in bits[:-1]:
                current = current.setdefault(bit, {})
            # Now assign value to current position
            try:
                current[bits[-1]] = v
            except TypeError:  # Special-case if current isn't a dict.
                current = {bits[-1]: v}

    def with_lists(self):
        return dict_list(self)


def build_Q(rules):
    """
    Build and requrn a Q object for a list of rule dictionaries
    """
    q_list = []
    for rule in rules:
        nm = rule['field'].replace('-', '_')
        q_list.append(Q(**{
            f"{rule['field']}__{rule['operator']}": rule['value']
        }))
    qRule = q_list.pop(0)
    for item in q_list:
        qRule |= item

    return qRule


def _get_nested(obj, fields, required=True):
    if required:
        a = obj[fields.pop(0)]
    else:
        a = obj.get(fields.pop(0), None)
    if not len(fields):
        return a
    else:
        return _get_nested(a, fields)


def get_nested(obj, field_name, required=True):
    """
    A dictionary implementation which supports extended django field names syntax
    such as employee__person__last_name.
    """
    if field_name == '*':
        return obj  # interpret special character '*' as pointing to self
    else:
        return _get_nested(obj, field_name.split('__'), required)


def get_nested_list(obj, field_names, required=True):
    """
    Get for a list of extended fields.
    """
    return [get_nested(obj, field_name, required) for field_name in field_names]


def flatten_dict(d, parent_key=''):
    items = []
    for k, v in list(d.items()):
        k = k.replace('-', '_')
        new_key = parent_key + FIELD_SEPARATOR + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(list(flatten_dict(v, new_key).items()))
        else:
            items.append((new_key, v))
    return dict(items)


FIELD_OPERATOR_CHOICES = [
    ("lt", "Less than"),
    ("gt", "Greater than"),
    ("lte", "Equal or Less than"),
    ("gte", "Equal or Greater than"),
    ("exact", "Exactly"),
    ("iexact", "Exactly (Any case)"),
    ("neq", "Not Equal to"),
    ("in", "Contained In"),
    ("contains", "Contains"),
    ("nin", "Not Contained In"),
    ("startswith", "Starts With"),
    ("endswith", "Ends With"),
    ("istartswith", "Starts With (Any case)"),
    ("iendswith", "Ends With (Any case)"),
    ("isnull", "Is Empty"),
    ("notnull", "Is Not Empty"),
]

FIELD_OPERATORS = {
    "lt": operator.lt,
    "lte": operator.le,
    "exact": operator.eq,
    "iexact": lambda x, y: operator.eq(x.lower(), y.lower()),
    "neq": operator.ne,
    "gte": operator.ge,
    "eq": operator.eq,
    "gt": operator.gt,
    "in": lambda x, y: operator.contains(y, x),
    "contains": operator.contains,
    "range": lambda x, y: y[0] <= x <= y[1],
    "startswith": lambda x, y: x.startswith(y),
    "istartswith": lambda x, y: y.lower().startswith(x.lower()),
    "endswith": lambda x, y: x.startswith(y),
    "iendswith": lambda x, y: x.lower().startswith(y.lower()),
    "nin": lambda x, y: not operator.contains(x, y),
    'isnull': lambda x, y: False if x else True,
    'notnull': lambda x, y: True if x else False,
}


class Queryable(object):
    """Converts a dictionary into an object which can be queried using django 
    Q objects"""

    def __init__(self, D):
        self.data = flatten_dict(D)

    def matches(self, q):
        if isinstance(q, tuple):
            key, value = q
            parts = key.split(FIELD_SEPARATOR)
            if parts[-1] in list(FIELD_OPERATORS.keys()):
                field_name = FIELD_SEPARATOR.join(parts[:-1])
                field_operator = FIELD_OPERATORS[parts[-1]]
                # operator_name = parts[-1]
            else:
                field_name = FIELD_SEPARATOR.join(parts)
                field_operator = FIELD_OPERATORS['exact']
                # operator_name = 'exact'
            if not field_name in self.data:
                return False
            else:
                field_value = self.data[field_name]
            return field_operator(field_value, value)
        elif isinstance(q, Q):
            if q.connector == 'OR':
                return any(self.matches(c) for c in q.children)
            elif q.connector == 'AND':
                return all(self.matches(c) for c in q.children)
        elif isinstance(q, bool):
            return q
        else:
            return False


def get_process_reqs(wf_spec):
    def _get(v):
        return isinstance(v, dict) and list(v.values()) or [v]

    var_lists = itertools.chain.from_iterable([t.get('uses', []) for t in list(wf_spec['tasks'].values())])
    new_reqs = set(itertools.chain.from_iterable(_get(e) for e in var_lists))
    return list(new_reqs)


def get_task_reqs(name, wf_reqs):
    reqs = []
    for itm in wf_reqs:
        parts = itm.split(FIELD_SEPARATOR)
        if name == parts[0]:
            reqs.append(FIELD_SEPARATOR.join(parts[1:]))
    return reqs


def build_url(*args, **kwargs):
    get = kwargs.pop('get', {})
    url = reverse(*args, **kwargs)
    if get:
        url += '?' + urllib.parse.urlencode(get)
    return url