#!/usr/bin/python -tt
import logging
import time
from datetime import datetime


"""
enm-client-scripting private module: poller

This is a private module and should not be used outside of the client-scripting module.
"""

logger = logging.getLogger(__name__)


class Poller(object):
    """
    Class used to calculate the polling intervals and sleep between polling.

    Example usage:
        poller = Poller(timeout=10)
        while poller.poll():
            # Do something
    """
    def __init__(self, timeout=600, sleep_time=0.1, sleep_multiplier=2, sleep_cap=1):
        """
        Initializes a Poller object.

        Keyword arguments:
        timeout - timeout in seconds after which the poll should stop (default 600)
        sleep_time - time to sleep in seconds between polls (default 0.1)
        sleep_multiplier - multiplier to be applied to the sleep_time after each poll (default 2)
        sleep_cap - cap amount time to sleep between polls (default 1)

        For example, default values will result in the following sleep times: [0, 0.1, 0.2, 0.4, 0.8, 1, 1, ...]
        """
        self._start_time = None
        self._timeout_seconds = timeout
        self._sleep_time = sleep_time
        self._sleep_multiplier = sleep_multiplier
        self._sleep_cap = sleep_cap
        self._current_sleep_time = self._sleep_time

    def poll(self):
        if self.start():
            return True
        elif self._timeout():
            logger.debug('Polling timeout [%s seconds] reached', str(self._timeout_seconds))
            return False
        else:
            logger.debug('Sleeping [%s seconds] before next poll', str(self._current_sleep_time))
            time.sleep(self._current_sleep_time)
            self._update_sleep_time()
            return True

    def reset(self, timeout=600):
        self._start_time = None
        self._timeout_seconds = timeout
        self._current_sleep_time = self._sleep_time
        logger.debug('Poller is reset, timeout is [%s seconds]', str(timeout))

    def start(self):
        """
        Starts the poller and sets the timer.

        Calling start() is optional, it is called implicitly at the first poll()
        """
        if self._start_time is None:
            self._start_time = datetime.now()
            return True
        return False

    def _timeout(self):
        return (datetime.now() - self._start_time).seconds >= self._timeout_seconds

    def _update_sleep_time(self):
        if self._current_sleep_time < self._sleep_cap:
            self._current_sleep_time = min(self._sleep_multiplier * self._current_sleep_time, self._sleep_cap)
