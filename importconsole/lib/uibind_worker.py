from threading import Thread, Event
import uuid
import logging

logger = logging.getLogger(__name__)


class Worker(object):

    def __init__(self):
        self._event = Event()
        self._work = None
        self._thread = Thread(target=self._do_work, name='UI-worker-Thread')
        self._thread.daemon = True
        self._thread.start()

    def _do_work(self):
        while bool(self._event.wait()) in (True, False):
            self._event.clear()
            work = self._work
            if work:
                try:
                    work._call()
                except Exception as e:
                    logger.exception('Exception executing background task. %s', e)
                work._ended = True

    def request(self, call):
        work = Work(uuid.uuid4(), call)
        self._work = work
        self._event.set()
        return work.get_id()

    def get_work_for(self, work_id):
        work = self._work
        return work if work.get_id() == work_id else None


class Work(object):

    def __init__(self, id, call):
        self._call = call
        self._id = id
        self._ended = False

    def get_id(self):
        return self._id

    def is_ended(self):
        return self._ended
