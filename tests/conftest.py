import functools
import sys
from contextlib import contextmanager
from io import StringIO


@contextmanager
def does_not_raise():
    yield


def redirect_stdout(decorated_function):
    @functools.wraps(decorated_function)
    def wrapper(*args):
        sys.stdout = StringIO()
        sys.stdout = sys.__stdout__
        decorated_function(*args)
    return wrapper
