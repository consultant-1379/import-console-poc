import datetime
import logging

from nose import with_setup
from enmscripting.private.poller import Poller
from . import restore_sleep, disable_sleep

logging.basicConfig()
logging.getLogger().setLevel(level=logging.DEBUG)


@with_setup(restore_sleep, disable_sleep)
def test_poller_default_values():
    poller = Poller(timeout=5)
    assert poller._start_time is None

    default_polling_times = [0.1, 0.1, 0.2, 0.4, 0.8, 1, 1, 1, 1]

    for sleep_time in default_polling_times:
        assert poller._current_sleep_time == sleep_time
        assert poller.poll() is True
        assert poller._start_time is not None

    assert poller.poll() is False


@with_setup(restore_sleep, disable_sleep)
def test_poller_flat():
    poller = Poller(timeout=3, sleep_time=1, sleep_multiplier=1)

    polling_times = [1, 1, 1, 1]

    for sleep_time in polling_times:
        assert poller._current_sleep_time == sleep_time
        assert poller.poll() is True
        assert poller._start_time is not None

    assert poller.poll() is False


def test_poller_reset():
    poller = Poller()
    assert poller._start_time is None
    assert poller._current_sleep_time == 0.1

    assert poller.poll() is True
    assert poller._start_time is not None
    assert poller.poll() is True
    assert poller._current_sleep_time != 0.1

    poller.reset()
    assert poller._start_time is None
    assert poller._current_sleep_time == 0.1


def test_poller_cap_5():
    poller = Poller(timeout=float('inf'), sleep_time=1, sleep_cap=5)

    polling_times = [1, 1, 2, 4, 5, 5, 5, 5, 5]

    for sleep_time in polling_times:
        assert poller._current_sleep_time == sleep_time
        poller.poll()


def test_poller_cap_infinity():
    poller = Poller(timeout=float('inf'), sleep_time=1, sleep_cap=float('inf'))
    polling_times = [1, 1, 2, 4, 8, 16]

    for sleep_time in polling_times:
        assert poller._current_sleep_time == sleep_time
        poller.poll()


@with_setup(restore_sleep, disable_sleep)
def test_poller_timeout_infinity():
    poller = Poller(timeout=float('inf'))
    for _ in range(4):
        assert poller.poll() is True
