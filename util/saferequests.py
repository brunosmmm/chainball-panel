import requests
from collections import namedtuple
from kivy.logger import Logger

SafeRetVal = namedtuple('SafeRetVal', ['success', 'data'])

def safe_post(*args, **kwargs):

    success = False
    ret = None
    try:
        ret = requests.post(*args, **kwargs)
        success = True
    except Exception as ex:
        Logger.warning('SafeRequests: caught an exception: {}'.format(repr(ex)))
        ret = ex

    return SafeRetVal(success, ret)

def safe_get(*args, **kwargs):

    success = False
    ret = None
    try:
        ret = requests.get(*args, **kwargs)
        success = True
    except Exception as ex:
        Logger.warning('SafeRequests: caught an exception: {}'.format(repr(ex)))
        ret = ex

    return SafeRetVal(success, ret)

def is_connection_error_exception(ex):

    for ex_type in (requests.exceptions.ConnectionError,
                    requests.exceptions.ConnectTimeout,
                    requests.exceptions.ReadTimeout):
        if isinstance(ex, ex_type):
            return True

    return False
