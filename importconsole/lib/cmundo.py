import json
import logging

from posixpath import join as urljoin

logger = logging.getLogger(__name__)

_HAL_JSON_CONTENT_TYPE = {'Content-type': 'application/json'}


class CmImportUndo(object):

    _JOBS_URI = '/configuration/jobs'
    _JOB_TYPE = 'UNDO_IMPORT_TO_LIVE'

    def __init__(self, nbi_session):
        self._session = nbi_session
        self._import_to_undo_cache = None

    def get_jobs(self, for_import_job=None):
        response = self._session.get(self._JOBS_URI, parameters={'type': self._JOB_TYPE}, headers=_HAL_JSON_CONTENT_TYPE)
        jobs = self._job_list_from_response(response)
        self._map_import_to_undo(jobs)
        logger.debug('job list is %s', str(jobs))

        return jobs if for_import_job is None else [j for j in jobs if j.job_id() == for_import_job]

    def get_job(self, undo_job_id):
        response = self._session.get(urljoin(self._JOBS_URI, str(undo_job_id)), parameters={'type': self._JOB_TYPE}, headers=_HAL_JSON_CONTENT_TYPE)
        return ImportUndoJob(self._session, **response)

    def get_job_for_import(self, import_job_id):
        if self._import_to_undo_cache is None:
            self.get_jobs()
        return self._import_to_undo_cache.get(import_job_id, [])

    def undo_import_job(self, import_job_id):
        data = {'type': self._JOB_TYPE, 'id': import_job_id, 'fileFormat': '3GPP'}
        response = self._session.post(self._JOBS_URI, request_body=json.dumps(data), headers=_HAL_JSON_CONTENT_TYPE)
        job_id = response['id']
        if self._import_to_undo_cache is None:
            self._import_to_undo_cache = {}
        undo_list = self._import_to_undo_cache.get(str(import_job_id), [])
        undo_list.append(job_id)
        self._import_to_undo_cache[str(import_job_id)] = undo_list

        return job_id

    def _job_list_from_response(self, json_response):
        list_of_jobs = []
        for job in json_response['jobs']:
            if job['type'] == self._JOB_TYPE:
                list_of_jobs.append(ImportUndoJob(self._session, **job))
        return list_of_jobs

    def _map_import_to_undo(self, undo_jobs_list):
        self._import_to_undo_cache = {}
        for job in undo_jobs_list:
            if not job.job_id() or not job.job_id().isdigit():
                continue
            undo_list = self._import_to_undo_cache.get(job.job_id(), [])
            undo_list.append(job.id())
            self._import_to_undo_cache[job.job_id()] = undo_list


class ImportUndoJob(object):

    def __init__(self, nbi_session, id, status='', statusReason='', type='', creationTime='', startTime='', endTime='', lastUpdateTime='',
                 userId='', jobId='', undoOperations='0', totalOperations='0', fileUri='', _links=None):
        self._links = _links
        self._file_uri = self._fix_context_uri(fileUri)
        self._total_operations = totalOperations
        self._undo_operations = undoOperations
        self._job_id = jobId
        self._user_id = userId
        self._last_update_time = lastUpdateTime
        self._end_time = endTime
        self._start_time = startTime
        self._creation_time = creationTime
        self._type = type
        self._status_reason = statusReason
        self._status = status
        self._id = id
        self._nbi_session = nbi_session

    def id(self):
        return self._id

    def status(self):
        return self._status

    def status_reason(self):
        return self._status_reason

    def type(self):
        return self._type

    def creation_time(self):
        return self._creation_time

    def start_time(self):
        return self._start_time

    def end_time(self):
        return self._end_time

    def last_update_time(self):
        return self._last_update_time

    def user_id(self):
        return self._user_id

    def job_id(self):
        return self._job_id

    def undo_operations(self):
        return self._undo_operations

    def total_operations(self):
        return self._total_operations

    def file_uri(self):
        return self._file_uri

    def is_successful(self):
        return self._status == 'COMPLETED'

    def save_file(self, dest_file):
        if not self._file_uri:
            raise ValueError('There is not file available to download.')
        header = _HAL_JSON_CONTENT_TYPE.copy()
        header.update({'Accept': 'application/octet-stream, application/json, application/hal+json'})
        response = self._nbi_session.send_request(self._nbi_session.get_method, path=self._file_uri, stream=True, headers=header)
        for block in response.iter_content(1024):
            if not block:
                break
            dest_file.write(block)

    @staticmethod
    def _fix_context_uri(uri):
        if uri and uri.startswith('/configuration') and not uri.startswith('/configuration/'):
            return '/configuration/' + uri[len('/configuration'):]
        return uri