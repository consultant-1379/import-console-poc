#!/usr/bin/python -tt
import logging
from ..common.element import *
from ..common.output import Output
from ..common.output import OutputFactory
from ..exceptions import IllegalStateException
from ..private.executionhandler import ExecutionHandler

logger = logging.getLogger(__name__)


class EnmCommand():
    """
    This class allows for the execution of a CLI command towards an ENM deployment. The return is a
    CommandOutput instance which holds the converted results
    """

    _SERVER_VERSION = 'VERSION=\"2\"'
    _CONTENT_TYPE = "application/vnd.com.ericsson.oss.scripting.command+json"
    _MEDIA_TYPE = _CONTENT_TYPE + ';' + _SERVER_VERSION

    def __init__(self, session):
        self._handler = ExecutionHandler(session, CommandOutputFactory(), self._MEDIA_TYPE)

    def execute(self, command_str, file=None, timeout_seconds=600):
        """
        :param command_str:      command to be executed. For more information about a command's syntax, please
                                    check the web-cli online help
        :param file:             file object to be imported  - optional parameter
                                    - needed if the command requires a file for upload
        :param timeout_seconds: number of seconds before a timeout will occur on a command. Default value = 600 seconds
        :return:                 CommandOutput instance
        """
        logger.debug('Executing EnmCommand command...')
        return self._handler.execute(command_str, file, timeout_seconds)


class CommandOutput(Output):
    """
    Class representing the output of the command execution in an object-friendly format
    """

    _OUTPUT = 'output'
    _COMMAND = 'command'
    _VERSION = 'v'

    def __init__(self, http_code, success, json_response=None, handler=None):
        """
        :param http_code:       http_response code
        :param success:
        :return:
        """
        self._command = None
        self._output = None
        self._files_cache = None

        super(CommandOutput, self).__init__(http_code, success, json_response, handler)

    def _process_complete_json(self, json):
        # Extract command string from JSON response
        if self._COMMAND in json:
            self._command = json[self._COMMAND]

    def has_files(self):
        """
        :return boolean: true if there are files in the response
        """
        return len(self.files()) > 0

    def files(self):
        """
        Gets all of the file elements in the output of the command

        :return ElementGroup: file elements
        """
        if self._files_cache is None:
            self._files_cache = self.get_output()._find_by_type(FileElement)
        return self._files_cache

    def get_output(self):
        """
        Gets the output of the command

        :return ElementGroup: the output of the command
        """
        logger.debug('get_output()')

        if not self._success:
            logger.warn('There is no output to parse, because command execution failed: raising IllegalStateException')
            raise IllegalStateException('There is no output to parse, because command execution failed')

        self._error_if_not_completed()

        if self._output is None:
            self._output = self._create_elements(self._parsed_json[self._OUTPUT])

        return self._output


class CommandOutputFactory(OutputFactory):
    """
        Class instantiating an instance of CommandOutput
    """

    def __init__(self):
        super(CommandOutputFactory, self).__init__()

    def create_output(self, http_code, success, json_response=None, handler=None):
        return CommandOutput(http_code, success, json_response, handler)
