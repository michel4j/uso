

import time
from collections import defaultdict
from importlib import import_module

from django.conf import settings
from django.db import models
from django.http.request import HttpRequest
from django.db.models.deletion import Collector


class Joiner(object):
    def __init__(self, main=', ', last=' and '):
        self.main = main
        self.last = last

    def __call__(self, item_list):
        items = list(map(str, item_list))
        return self.main.join(items) if len(items) <= 1 else self.last.join([self.main.join(items[:-1]), items[-1]])


def flatten(*args):
    return [
        e for a in args
        for e in (flatten(*a) if isinstance(a, (tuple, list)) else (a,))
    ]


class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)


class memoize_for(object):
    """Memoize for a given duration"""
    _caches = {}
    _timeouts = {}

    def __init__(self, minutes=2):
        self.duration = minutes * 60

    def collect(self):
        """Clear cache of results which have timed out"""
        for func in self._caches:
            cache = {}
            for key in self._caches[func]:
                if (time.time() - self._caches[func][key][1]) < self._timeouts[func]:
                    cache[key] = self._caches[func][key]
            self._caches[func] = cache

    def __call__(self, f):
        self.cache = self._caches[f] = {}
        self._timeouts[f] = self.duration

        def func(*args, **kwargs):
            kw = sorted(kwargs.items())
            key = (args, tuple(kw))
            try:
                v = self.cache[key]
                if (time.time() - v[1]) > self.duration:
                    raise KeyError
            except KeyError:
                v = self.cache[key] = f(*args, **kwargs), time.time()
            return v[0]

        func.__name__ = f.__name__
        return func


def get_module(app, modname, verbose, failfast):
    """
    Internal function to load a module from a single app.
    """
    module_name = f'{app}.{modname}'
    try:
        module = import_module(module_name)
    except ImportError as e:
        if failfast:
            raise e
        elif verbose:
            print("Could not load {!r} from {!r}: {}".format(modname, app, e))
        return None
    if verbose:
        print("Loaded {!r} from {!r}".format(modname, app))
    return module


def load(modname, verbose=False, failfast=False):
    """
    Loads all modules with name 'modname' from all installed apps.

    If verbose is True, debug information will be printed to stdout.

    If failfast is True, import errors will not be surpressed.
    """
    for app in settings.INSTALLED_APPS:
        get_module(app, modname, verbose, failfast)


def iterload(modname, verbose=False, failfast=False):
    """
    Loads all modules with name 'modname' from all installed apps and returns
    and iterator of those modules.

    If verbose is True, debug information will be printed to stdout.

    If failfast is True, import errors will not be surpressed.
    """
    for app in settings.INSTALLED_APPS:
        module = get_module(app, modname, verbose, failfast)
        if module:
            yield module


def load_object(import_path):
    """
    Loads an object from an 'import_path', like in MIDDLEWARE_CLASSES and the
    likes.

    Import paths should be: "mypackage.mymodule.MyObject". It then imports the
    module up until the last dot and tries to get the attribute after that dot
    from the imported module.

    If the import path does not contain any dots, a TypeError is raised.

    If the module cannot be imported, an ImportError is raised.

    If the attribute does not exist in the module, a AttributeError is raised.
    """
    if '.' not in import_path:
        raise TypeError(
            "'import_path' argument to 'misc.utils.load_object' must "
            "contain at least one dot."
        )
    module_name, object_name = import_path.rsplit('.', 1)
    module = import_module(module_name)
    return getattr(module, object_name)


def iterload_objects(import_paths):
    """
    Load a list of objects.
    """
    for import_path in import_paths:
        yield load_object(import_path)


def is_ajax(request: HttpRequest) -> bool:
    """
    https://stackoverflow.com/questions/63629935
    """
    return (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or request.accepts("application/json")
    )