import os
import json
import logging
import time
import fcntl

from threading import Thread, Lock

_1_HOUR_IN_SECONDS = 60 * 60

_1_DAY_IN_SECONDS = 24 * _1_HOUR_IN_SECONDS

_30_DAYS = 30

logger = logging.getLogger(__name__)


class FileCleaner(object):

    def __init__(self, registry_root, cm_import, interval_seconds=_1_HOUR_IN_SECONDS, error_retention_days=_30_DAYS):
        self._error_retention_days = error_retention_days * _1_DAY_IN_SECONDS
        self._cm_import = cm_import
        self._interval = interval_seconds
        self._registry_root = registry_root or os.curdir
        self._thread_lock = Lock()
        self._request_repo = _RequestRepository(registry_root)
        if interval_seconds > 0:
            self._thread = Thread(target=self._do_work, name='File-Cleaner-Thread')
            self._thread.daemon = True
            self._thread.start()

    def _do_work(self):
        lock_file = os.path.join(self._registry_root, '.c_lock')
        time.sleep(10)
        logger.debug('Starting FileCleaner job')
        with _FileLock(lock_file, attempt_interval=self._interval):
            logger.debug('[FileCleaner] got the lock to process files...')
            while True:
                self._clean_files()
                logger.debug('[FileCleaner] will sleep for %d seconds', self._interval)
                time.sleep(self._interval)

    def clean_files(self):
        lock_file = os.path.join(self._registry_root, '.c_lock')
        with _FileLock(lock_file, attempt_interval=30):
            logger.debug('[FileCleaner] got the lock to process files...')
            self._clean_files()

    def _clean_files(self):
        logger.debug('[FileCleaner] starting the clean up...')
        with self._thread_lock:
            for clean_request in self._request_repo.get_requests():
                if clean_request:
                    logger.debug('[FileCleaner] found clean request for job=[%s], file=[%s]', clean_request.job_id(), clean_request.job_file())
                    job_search = self._cm_import.get_jobs(job_id=clean_request.job_id())
                    if len(job_search) == 0:
                        logger.info('Could not find job with id [%s] on system, canceling cleanup request', clean_request.job_id())
                        clean_request.cancel()
                    else:
                        file_to_delete = os.path.basename(clean_request.job_file())
                        import_job = job_search[0]
                        if import_job.is_finished():
                            last_modified = os.path.getmtime(clean_request.job_file())
                            if import_job.has_errors() and time.time() - last_modified < self._error_retention_days:
                                logger.info('Not deleting file for job [%s], since job has failures', clean_request.job_id())
                            else:
                                if len([imp_file for imp_file in import_job.files() if imp_file.name() == file_to_delete]):
                                    clean_request.delete_and_cancel()
                                else:
                                    logger.error(
                                        "File [%s] won't be deleted since it does not match any file of the job [%s]",
                                        file_to_delete, import_job.id())
                                    clean_request.cancel()
                        else:
                            logger.debug('Import job [%s] is not finished yet, keeping file...')

    def add_file(self, job_id, file_path):
        self._request_repo.add_request(job_id, file_path)


class _FileLock(object):

    def __init__(self, lock_file, attempt_interval=_1_HOUR_IN_SECONDS):
        self._lock_file = lock_file
        self._lock_fd = None
        self._attempt_interval = attempt_interval

    def acquire(self):
        while True:
            if not self.is_locked():
                self._acquire()

            if self.is_locked():
                break
            else:
                time.sleep(self._attempt_interval)

    def release(self):
        self._release()

    def is_locked(self):
        return self._lock_fd is not None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
        return None

    def __del__(self):
        self.release()
        return None

    def _acquire(self):
        open_mode = os.O_RDWR | os.O_CREAT | os.O_TRUNC
        fd = os.open(self._lock_file, open_mode)
        try:
            os.fchmod(fd, 0666)
        except OSError:
            logger.debug('Failed to change lock file mode to 666')

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            os.close(fd)
        else:
            self._lock_fd = fd

    def _release(self):
        fd = self._lock_fd
        if fd:
            fcntl.flock(fd, fcntl.LOCK_UN)
            self._lock_fd = None
            os.close(fd)


class _CleanupRequest(object):

    def __init__(self, record_file, data):
        self._data = data
        self._record_file = record_file

    def job_id(self):
        return self._data.get('job_id')

    def job_file(self):
        return self._data.get('job_file')

    def delete_and_cancel(self):
        try:
            to_remove = self.job_file()
            if os.path.exists(to_remove):
                os.remove(to_remove)
                logger.info('[FileCleaner] File [%s] was removed', to_remove)
            else:
                logger.debug('[FileCleaner] File [%s] was not found, nothing to do here...', to_remove)
        except (IOError, OSError) as e:
            logger.exception('Failed to remove file %s: %s', self.job_file(), e)
        else:
            self.cancel()

    def cancel(self):
        try:
            logger.info('[FileCleaner] Cleanup request for job [%s] was canceled', self.job_id())
            os.remove(self._record_file)
        except (IOError, OSError) as e:
            logger.exception('Failed to remove file %s: %s', self._record_file, e)


class _RequestRepository(object):

    _FILE_EXTENSION = '.cleanup'

    def __init__(self, repository_path=None):
        self._repo_path = repository_path or os.curdir

    def add_request(self, job_id, file_path):
        record_name = '%s%s' % (job_id, self._FILE_EXTENSION)
        data = {'job_id': job_id, 'job_file': file_path}
        self._write_record(record_name, data)

    def get_requests(self):
        requests = []
        for record in self._list_records():
            data = self._load_record(record)
            requests.append(_CleanupRequest(self._with_repo_path(record), data))
        return requests

    def _list_records(self):
        records = []
        for file in os.listdir(self._repo_path):
            if file.endswith(self._FILE_EXTENSION):
                records.append(file)
        return records

    def _load_record(self, record_name):
        record_file = self._with_repo_path(record_name)
        data = None
        try:
            with open(record_file) as f:
                data = json.load(f)
        except IOError as e:
            logger.exception('Failed to open file %s: %s', record_name, e)
        return data

    def _write_record(self, record_name, data):
        record_file = self._with_repo_path(record_name)
        with open(record_file, 'w') as f:
            json.dump(data, f)

    def _with_repo_path(self, file_name):
        return os.path.join(self._repo_path, file_name)

