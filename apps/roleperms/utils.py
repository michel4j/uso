from __future__ import annotations

from typing import Sequence


def _getattr_related(obj, fields, silent=False):
    try:
        a = getattr(obj, fields.pop(0))
    except:
        if not silent: raise
        a = None
    if not len(fields):
        return a
    else:
        return _getattr_related(a, fields, silent)


def getattr_related(obj, field_name, silent=False):
    """
    A getattr implementation which supports extended django field names syntax
    such as employee__person__last_name.
    """
    if field_name == '*':
        return obj  # interpret special character '*' as pointing to self
    else:
        return _getattr_related(obj, field_name.split('__'), silent)


def getattr_related_list(obj, field_names, silent=False):
    """
    Getattr for a list of extended fields.
    """
    return [getattr_related(obj, field_name, silent) for field_name in field_names]


def has_any_items(target: Sequence, source: Sequence | set) -> bool:
    """
    Match any role permissions and permissions.
    """
    return len(target) == 0 or bool(set(target) & set(source))


def has_all_items(target: Sequence, source: Sequence | set) -> bool:
    """
    Match all role permissions and permissions.
    """
    return set(source) >= set(target)