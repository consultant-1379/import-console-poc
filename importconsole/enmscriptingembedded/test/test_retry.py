from enmscripting.private.retry import retry, on_fail_sleep
from nose.tools import assert_raises
import logging

logging.basicConfig()
logging.getLogger().setLevel(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# Attempts
def test_retry_success():
    t = TestRetry()
    result = t.do_retry_2()
    assert result == 1
    assert t.exec_times() == 1  # Success first time, no re-try


def test_retry_2_success():
    t = TestRetry(1)
    result = t.do_retry_2()
    assert result == 2
    assert t.exec_times() == 2  # Success second time


def test_retry_2_fail():
    t = TestRetry(5)
    assert_raises(ValueError, t.do_retry_2)
    assert t.exec_times() == 2


def test_retry_5_fail():
    t = TestRetry(10)
    assert_raises(ValueError, t.do_retry_5)
    assert t.exec_times() == 5


# Accept function
def test_accept_everything():
    t = TestRetry(10)
    assert_raises(ValueError, t.do_retry_2_accept_everything)
    assert t.exec_times() == 1  # No retry, even though there was an exception


def test_accept_nothing():
    t = TestRetry()
    result = t.do_retry_2_accept_nothing()
    assert result == 2
    assert t.exec_times() == 2  # Retry, even though function completed


def test_accept_nothing_lambda():
    t = TestRetry()
    result = t.do_retry_2_accept_nothing_lambda()
    assert result == 2
    assert t.exec_times() == 2  # Retry, even though function completed


# On fail function
def test_on_fail_sleep_default():
    t = TestRetry(10)
    assert_raises(ValueError, t.do_retry_2_sleep)
    assert t.exec_times() == 2


def test_on_fail_capture():
    t = TestRetry(10)
    assert_raises(ValueError, t.do_retry_2_capture)
    assert t.exec_times() == 2
    assert t.captured_failures() == 1  # number of calls - 1


def test_on_fail_lambda():
    t = TestRetry(10)
    assert_raises(ValueError, t.do_retry_2_on_fail_lambda)
    assert t.exec_times() == 2
    assert t.captured_failures() == 1  # number of calls - 1


# Combinations of parameters
def test_on_fail_capture_5_attempts():
    t = TestRetry(10)
    assert_raises(ValueError, t.do_retry_5_capture)
    assert t.exec_times() == 5
    assert t.captured_failures() == 4  # number of calls - 1


def test_5_attempts_capture_accept_nothing():
    t = TestRetry()
    result = t.do_retry_5_capture_accept_nothing()
    assert result == 5
    assert t.exec_times() == 5  # Retries, even though function completed
    assert t.captured_failures() == 4  # number of calls - 1


# Retry decorator twice
def test_retry_twice_equals():
    t = TestRetry(20)
    assert_raises(ValueError, t.do_retry_equal)
    assert t.exec_times() == 9  # 3 * 3


def test_retry_twice_disjunctive():
    t = TestRetry()
    result = t.do_retry_2_decorator_disjunctive()
    assert result == 10  # 5 + 5
    assert t.exec_times() == 10


class TestRetry(object):
    def __init__(self, fail_times=0):
        self._fail_times = fail_times
        self._exec_times = 0
        self._captured_failures = 0

    def _do_stuff(self):
        self._exec_times += 1
        logger.debug("Doing stuff [%s]", self._exec_times)
        if self._fail_times < self._exec_times:
            logger.debug("Stuff completed")
            return self.exec_times()
        else:
            raise ValueError("there is a problem")

    def exec_times(self):
        return self._exec_times

    def captured_failures(self):
        return self._captured_failures

    def accept_everything(response):
        return True

    def accept_nothing(response):
        return False

    def accept_first_5(response):
        return response <= 5

    def accept_after_5(response):
        return response > 5

    def on_fail_capture(result, attempts, *args, **kwargs):
        args[0]._captured_failures += 1

    @retry()
    def do_retry_2(self):
        return self._do_stuff()

    @retry(attempts=5)
    def do_retry_5(self):
        return self._do_stuff()

    @retry(accept_func=accept_everything)
    def do_retry_2_accept_everything(self):
        return self._do_stuff()

    @retry(accept_func=accept_nothing)
    def do_retry_2_accept_nothing(self):
        return self._do_stuff()

    @retry(accept_func=lambda result: False)
    def do_retry_2_accept_nothing_lambda(self):
        return self._do_stuff()

    @retry(on_fail_func=on_fail_sleep)
    def do_retry_2_sleep(self):
        return self._do_stuff()

    @retry(on_fail_func=on_fail_capture)
    def do_retry_2_capture(self):
        return self._do_stuff()

    @retry(on_fail_func=lambda result, attempts, *args: args[0].on_fail_capture(result, *args))
    def do_retry_2_on_fail_lambda(self):
        return self._do_stuff()

    @retry(attempts=5, on_fail_func=on_fail_capture)
    def do_retry_5_capture(self):
        return self._do_stuff()

    @retry(attempts=5, on_fail_func=on_fail_capture, accept_func=accept_nothing)
    def do_retry_5_capture_accept_nothing(self):
        return self._do_stuff()

    # The following are not recommended, because it can be tricky, no harm to test
    @retry(attempts=3)  # Multiplies if every call fails
    @retry(attempts=3)
    def do_retry_equal(self):
        return self._do_stuff()

    @retry(attempts=6, accept_func=accept_after_5)
    @retry(attempts=5, accept_func=accept_first_5)
    def do_retry_2_decorator_disjunctive(self):
        return self._do_stuff()
