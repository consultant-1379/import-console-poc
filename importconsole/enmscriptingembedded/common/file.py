#!/usr/bin/python -tt
import os


class FileResult(object):
    """
    Class representing a file available to download
    """

    # Make sure instances of this class remaining immutable.
    def __init__(self, application_id, file_id, execution_handler):
        self._application_id = application_id
        self._file_id = file_id
        self._execution_handler = execution_handler

    def download(self, path=None):
        """
        This downloads the file to the specified directory, or the current working directory
        if no path is provided

        If a directory, say '/my/directory' is provided, the file will be stored
        as '/my/directory/<remote-file-name>'

        :param path:            optional parameter  - path for location to store the downloaded file
                                                    - default is the current directory
        """
        self._execution_handler.download(self._application_id, self._file_id, path)

    def get_bytes(self):
        """
        This stores the file as a byte array in memory

        :return:                the file as a bytearray
        """
        return self._execution_handler.get_bytes(self._application_id, self._file_id)

    def get_name(self):
        """
        .. deprecated:: 1.11.1
        Deprecated since it can't reliably return the file name

        :return:                the file name
        """
        return os.path.basename(self._file_id)
