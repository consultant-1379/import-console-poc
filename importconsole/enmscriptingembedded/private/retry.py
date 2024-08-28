import logging

import sys
import functools
from .poller import Poller

"""
enm-client-scripting private module: retry

This is a private module and should not be used outside of the client-scripting module.
"""

logger = logging.getLogger(__name__)


def retry(attempts=2, on_fail_func=None, accept_func=None):
    """
    Decorator to support re-try

    Usage:
    @retry()  # Using re-try with default behaviour
    def my_function():
        pass

    Examples:
    @retry(attempts=5)  # Specify the number of attempts to be made before giving up
    @retry(accept_func=accept_everything)  # Specify the function that decides if result can be accepted or not
    @retry(on_fail_func=on_fail_sleep)  # Specify the function to be called if result is not accepted (eg sleep)

    Examples with lambda functions:
    @retry(accept_func=lambda result: False)  # lambda function that rejects every result
    @retry(on_fail_func=lambda result, attempts, *args: args[0].on_fail_capture(result, *args))

    :param attempts: number of attempts to be made before giving up
    :param on_fail_func: function to call if execution fails
    :param accept_func: function that returns a boolean whether the result is accepted or not
    :return: function
    """
    def _retry(func):
        # TODO: Consider change the retry to be "timeout" driven instead of number of "attempts"
        def _wrap(*args, **kwargs):
            return Retry(attempts, on_fail_func, accept_func).call(func, *args, **kwargs)
        _wrap = functools.wraps(func, assigned=functools.WRAPPER_ASSIGNMENTS, updated=functools.WRAPPER_UPDATES)(_wrap)
        _wrap.__wrapped__ = func
        return _wrap
    return _retry


def on_fail_sleep(result, poller, *args, **kwargs):
    if poller is None:  # Means this is the first attempt
        poller = Poller(timeout=float('inf'), sleep_time=2, sleep_multiplier=2, sleep_cap=float('inf'))
        poller.start()
    poller.poll()
    return poller


class Retry(object):
    def __init__(self, attempts=2, on_fail_func=None, accept_func=None):
        if attempts is not None:
            self.attempts = attempts
        if on_fail_func is not None:
            self.on_fail = on_fail_func
        if accept_func is not None:
            self.accept = accept_func

    def abandon(self, attempts):
        return attempts >= self.attempts

    @staticmethod
    def accept(result):
        return not isinstance(result, Exception)

    @staticmethod
    def on_fail(result, attempts, *args, **kwargs):
        return

    def call(self, f, *args, **kwargs):
        attempts = 0
        on_fail_return_object = None

        while True:
            try:
                attempts += 1
                result = Result(f(*args, **kwargs))
            except Exception:
                result = Result(sys.exc_info(), True)  # exc_info is used to keep the stacktrace

            if self.accept(result.get_result()):
                return result.return_raise_result()

            logger.debug("Function [%s] call failed", f.__name__)

            if self.abandon(attempts):
                logger.debug("Giving up [%s] after [%s] attempts, returning or raising result", f.__name__, attempts)
                return result.return_raise_result()

            on_fail_return_object = self.on_fail(result.get_result(), on_fail_return_object, *args, **kwargs)
            logger.debug("Re-trying function call [%s]", f.__name__)


class Result(object):
    """
    Result object that wraps the result
    """
    def __init__(self, result, is_exception=False):
        self._result = result
        self._is_exception = is_exception

    def get_result(self):
        if self._is_exception:
            # Exception is stored as a tuple: (<type>, <exception instance>, <trace object>)
            # Returning the exception
            return self._result[1]
        else:
            return self._result

    def return_raise_result(self):
        if self._is_exception:
            # raise like this is required to keep the original call's stack trace
            raise self._result[0], self._result[1], self._result[2]
            # The above is incompatible with Python 3, install six and replace raise with this:
            # six.reraise(self._result[0], self._result[1], self._result[2])
        else:
            return self._result
