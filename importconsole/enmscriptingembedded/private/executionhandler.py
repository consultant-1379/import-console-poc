#!/usr/bin/python -tt
import logging
import io
import os
from posixpath import join as urljoin
from .poller import Poller
from ..exceptions import *
from threading import Lock
try:
    range = xrange  # Python 2
except NameError:
    pass  # Python 3 xrange was renamed to range

"""
enm-client-scripting private module: executionhandler

This is a private module and should not be used outside of the client-scripting module.
"""

logger = logging.getLogger(__name__)


class _IdGenerator(object):

    def __init__(self):
        self.id_root = str(os.getpid()) + '.'
        self.count = 0
        self.lock = Lock()

    def new_id(self):
        with self.lock:
            self.count += 1
            return self.id_root + str(self.count)


_handler_id_generator = _IdGenerator()


class ExecutionHandler:
    """
    Class to contain the execution of the ENM Command.
    """

    # SERVER-SCRIPTING URLS
    _PATH_SS = urljoin('server-scripting', 'services')  # server-scripting/services
    _PATH_FILE = urljoin(_PATH_SS, 'file')  # server-scripting/services/file
    _PATH_POST = urljoin(_PATH_SS, 'command')  # server-scripting/services/command
    _PATH_GET = urljoin(_PATH_POST, 'output')  # server-scripting/services/command/output

    # Post data keys: req_data / file_data
    _POST_DATA_NAME = 'name'
    _POST_DATA_FILE = 'file:'
    _POST_DATA_COMMAND = 'command'
    _POST_DATA_FILE_NAME = 'fileName'
    _POST_DATA_REQ_SEQUENCE = 'requestSequence'
    _POST_DATA_STREAM_FLAG = 'stream_output'

    # URL parameter
    _REQUEST_ID = '_requestId'
    _GET_WAIT_MILLI = '_wait_milli'
    _STREAM = 'stream'

    # Headers
    _HEADER_DEFAULT = {'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': ', '.join(('gzip', 'deflate', 'sdch'))}
    _HEADER_CONTENT_TYPE_FILE = {'Accept': 'application/octet-stream'}
    _HEADER_CONTENT_TYPE_POST_TEXT = {'Accept': 'application/vnd.com.ericsson.oss.scripting+text;VERSION="1"'}
    _HEADER_CONTENT_TYPE_GET_TEXT = {'Accept': 'application/vnd.com.ericsson.oss.scripting.terminal+json;VERSION="3"'}

    _KEY_GET = 'get'
    _KEY_POST = 'post'
    _KEY_FILES = 'files'

    # Polling parameters
    _POLL_TIMEOUT = 600
    _POLL_SLEEP_TIME = 0.1
    _POLL_SLEEP_MULTIPLIER = 2
    _POLL_SLEEP_CAP = 1

    def __init__(self, session=None, output_factory=None, result_media_type=_HEADER_CONTENT_TYPE_GET_TEXT):
        """
        Default
        """
        if session is not None:
            self._url = session.url()
        else:
            self._url = ''

        self._session = session
        self._output_factory = output_factory
        self._headers = {self._KEY_GET:   self._merge(self._HEADER_DEFAULT, {'Accept': result_media_type}),
                         self._KEY_POST:  self._merge(self._HEADER_DEFAULT, self._HEADER_CONTENT_TYPE_POST_TEXT),
                         self._KEY_FILES: self._merge(self._HEADER_DEFAULT, self._HEADER_CONTENT_TYPE_FILE)}

        self._urls = {self._KEY_GET:   urljoin(self._url, self._PATH_GET),
                      self._KEY_POST:  urljoin(self._url, self._PATH_POST),
                      self._KEY_FILES: urljoin(self._url, self._PATH_FILE)}

        self._allow_redirects = True
        self._last_request_id = "new"
        self._instance_id = _handler_id_generator.new_id()
        self._request_lock = Lock()
        self._poller = Poller(timeout=self._POLL_TIMEOUT,
                              sleep_time=self._POLL_SLEEP_TIME,
                              sleep_multiplier=self._POLL_SLEEP_MULTIPLIER,
                              sleep_cap=self._POLL_SLEEP_CAP)

    def execute(self, command_str, file=None, timeout_seconds=600):
        """
        :param command_str:      command to be executed. For more information about a command's syntax, please
                                 check the web-cli online help
        :param file:             file object to be imported  - optional parameter -
                                 needed if the command requires a file for upload
        :param timeout_seconds:
        :return:                 Output instance
        """
        logger.debug('Starting execution of command....')
        with self._request_lock:
            response = self._command_post(command_str, file)
            if response.status_code is not 201:
                logger.warning('Failed to post command [%s]', command_str)
                return self._output_factory.create_output(response.status_code, False, response.text, self)
            self._last_request_id = response.text

            output = self._command_poll_get(timeout_seconds)
            logger.debug('Command executed successfully [%s], command response is complete', command_str)
            return output

    def download(self, application_id, file_id, path):
        logger.debug('Downloading file from ENM')
        response = self._command_download(application_id, file_id)

        full_file_name = self._file_path_and_name(response, file_id, path)
        with io.open(full_file_name, 'wb') as handle:
            for block in response.iter_content(1024):
                if not block:
                    break
                handle.write(block)
            logger.debug('Wrote file [%s] to disk', path)

    def get_bytes(self, application_id, file_id):
        logger.debug('Downloading file from ENM')
        response = self._command_download(application_id, file_id)
        buf = bytearray()
        for b in response.iter_content():
            if not b:
                break
            buf.extend(b)
        logger.debug('Wrote [%i] bytes to memory', len(buf))
        return buf

    def _command_post(self, command, file_in=None):
        logger.debug('POST command request')
        file_data, req_data = self._get_post_data(self._instance_id, command, file_in)
        response = self._session_post(file_data=file_data, req_data=req_data)
        logger.debug('POST command request executed')
        return response

    def _command_poll_get(self, timeout_seconds):
        logger.debug('Polling for command result')
        self._poller.reset(timeout_seconds)

        output = None
        wait_result_milli = 1000
        while self._poller.poll():
            response = self._command_get(self._last_request_id, wait_result_milli)
            if response.status_code is not 200:
                logger.warning('Failed to get result with request ID [%s]', self._last_request_id)
                return self._output_factory.create_output(response.status_code, False, response.text, self)
            if output:
                logger.debug('Appending partial response')
                output._append_response(response.text)
            else:
                output = self._output_factory.create_output(response.status_code, True, response.text, self)
            if output.is_complete():
                return output
            wait_result_milli = max(0, wait_result_milli - 500)

        logger.debug('Command did not complete within the specified timeout [%i seconds], '
                     'raising TimeoutException', timeout_seconds)
        raise TimeoutException('Command did not complete within the specified timeout [%i seconds]'
                               % timeout_seconds)

    def _command_get(self, _last_request_id, wait_milli=0):
        logger.debug('GET command result')
        logger.debug('The last request ID: ' + str(_last_request_id))
        response = self._session_get(_last_request_id, wait_milli)
        logger.debug('GET command result executed')
        return response

    def _command_download(self, application_id, file_id):
        response = self._session_files(application_id=application_id, file_id=file_id)
        if response.status_code is not 200:
            logger.error('Failed to download file [%s] with application id [%s]', str(file_id), str(application_id))
            logger.error('Server response is [%s]', str(response.text))
            raise InternalError('Failed to download file [%s] with application id [%s]'
                                % (str(file_id), str(application_id)))
        return response

    @classmethod
    def _merge(cls, *dict_args):
        result = {}
        for dictionary in dict_args:
            result.update(dictionary)
        return result

    @classmethod
    def _get_post_data(cls, instance_id, command, file_in=None):
        if file_in is not None:
            logger.debug('POST command contains file [%s]', file_in.name)
            file_name = cls._get_file_name(command, file_in)
            file_data = {cls._POST_DATA_FILE: (file_name, file_in)}
            req_data = {cls._POST_DATA_COMMAND: command, cls._POST_DATA_FILE_NAME: file_name,
                        cls._POST_DATA_STREAM_FLAG: "true",
                        cls._POST_DATA_REQ_SEQUENCE: instance_id}
        else:
            logger.debug('POST command does not contains file')
            file_data = {cls._POST_DATA_NAME: cls._POST_DATA_COMMAND,
                         cls._POST_DATA_COMMAND: command,
                         cls._POST_DATA_STREAM_FLAG: "true",
                         cls._POST_DATA_REQ_SEQUENCE: instance_id}
            req_data = None
        logger.debug('POST: file_data=%s, req_data=%s', file_data, req_data)
        return file_data, req_data

    @classmethod
    def _get_file_name(cls, command, file_in):
        file_name = os.path.basename(file_in.name)
        command_file_part = cls._POST_DATA_FILE + file_name
        if command_file_part not in command:
            logger.warn("Expected file name [file:%s] not found in command [%s]", file_name, command)
        return file_name

    def _session_post(self, file_data, req_data):
        return self._session.post(
            self._urls[self._KEY_POST],
            headers=self._headers[self._KEY_POST],
            files=file_data, data=req_data,
            allow_redirects=self._allow_redirects)

    def _session_get(self, _last_request_id, wait_milli=0):
        return self._session.get(
            self._get_request_url_for_get(self._urls[self._KEY_GET], _last_request_id, wait_milli),
            headers=self._headers[self._KEY_GET],
            allow_redirects=self._allow_redirects)

    def _session_files(self, application_id, file_id):
        return self._session.get(
            self._get_request_url(self._urls[self._KEY_FILES], '/'.join((str(application_id), str(file_id)))),
            headers=self._headers[self._KEY_FILES],
            stream=True)

    def _get_request_url(self, url, *args):
        for arg in args:
            url = urljoin(url, str(arg).lstrip('/'))
            logger.debug("Argument [%s] is added to url", str(arg))

        url = "%s?%s=%s" % (url, self._REQUEST_ID, self._last_request_id)

        logger.debug("Generated URL with arguments and request_id is [%s]", url)
        return url

    def _get_request_url_for_get(self, url, last_request_id, wait_milli=0):
        url = urljoin(url, last_request_id, self._STREAM)

        if wait_milli:
            url = "%s?%s=%s" % (url, self._GET_WAIT_MILLI, wait_milli)

        logger.debug("Generated URL [%s] for get call with request_id [%s]", url, last_request_id)
        return url

    def _file_path_and_name(self, response, file_id, path):
        if path is not None and not os.path.isdir(path):
            final_path = path
        else:
            file_name = self._file_name_from_header(response)
            if not file_name:
                file_name = file_id
                logger.debug('NO file name found in the headers, will use the file ID as name.')

            if path is None:
                final_path = file_name
            else:
                final_path = path + os.path.sep + file_name

        return final_path

    @classmethod
    def _file_name_from_header(cls, response):
        if 'Content-Disposition' in response.headers:
            content_disp = dict(map(lambda x: x.strip().split('=') if '=' in x else (x.strip(), ''),
                                    response.headers['Content-Disposition'].split(';')))
            if 'filename' in content_disp:
                filename = content_disp['filename'].strip("\"'")
                if filename:
                    return filename
        return ''
