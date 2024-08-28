import io
import requests
import os
import logging
from nose.tools import assert_raises
from mock import MagicMock, ANY, patch
from requests.exceptions import ConnectionError
from enmscripting import *
from enmscripting.common.file import FileResult
from enmscripting.private.executionhandler import ExecutionHandler
from enmscripting.command.command import EnmCommand
from enmscripting.terminal.terminal import TerminalOutputFactory
from enmscripting.test.json_generator import generate_json

logging.basicConfig()
logging.getLogger().setLevel(level=logging.DEBUG)

_MEDIA_TYPE = "application/vnd.com.ericsson.oss.scripting.command+json;VERSION=\"1\""
_FILE_PATH = './abc.txt'
_FILE_CONTENT = 'fileContent'


def test_execute_post():
    handler = ExecutionHandler(output_factory=TerminalOutputFactory())
    set_command_mock(handler, post_res_code=201, get_res_code=200)
    handler.execute('command')
    handler._session.post.assert_called_with(
        ANY, headers=ANY, files=ANY, data=None, allow_redirects=True)


def test_command_post_with_file():
    handler = ExecutionHandler(output_factory=TerminalOutputFactory())
    set_command_mock(handler, post_res_code=201, get_res_code=200)

    with io.open("valid.txt", "wb+") as fileUpload:
        fileUpload.write(b'dummyNode')
        handler.execute('secadm command file:valid.txt', fileUpload)
        handler._session.post.assert_called_with(
            ANY, headers=ANY, files=ANY, data=ANY, allow_redirects=True)

    if os.path.isfile(fileUpload.name):
        os.remove(fileUpload.name)


def test_instance_must_have_different_identities():
    handler1 = ExecutionHandler()
    handler2 = ExecutionHandler()

    assert not handler1._instance_id == handler2._instance_id


def test_execute_post_exception():
    conn_error = ConnectionError('connection error')
    with patch.object(requests.session(), 'post') as session:
        session.post.side_effect = conn_error
        handler = ExecutionHandler(session)
        assert_raises(ConnectionError, handler.execute, 'command')
        assert session.post.call_count is 1


# DOWNLOAD TESTS

def mock_download_response(status_code=200):
    session = requests.session()
    session._verify = False
    r = requests.Response()
    r.iter_content = lambda chunk_size=1: iter(_FILE_CONTENT)
    r.status_code = status_code
    session.get = lambda *args, **kwargs: r
    session.url = lambda: 'fakeUrl'
    return session


def test_download():
    session = mock_download_response()
    handler = ExecutionHandler(session)
    handler.download('appId', 'fileId', _FILE_PATH)

    with io.open(_FILE_PATH, 'r+') as f:
        assert f.read() == _FILE_CONTENT
    os.remove(_FILE_PATH)


def test_download_with_no_filename_should_use_fileid():
    session = mock_download_response()
    handler = ExecutionHandler(session)
    handler.download('appId', 'fileId', None)

    assert os.path.exists('fileId')

    with io.open('fileId', 'r+') as f:
        assert f.read() == _FILE_CONTENT
    os.remove('fileId')


def test_download_with_no_filename_but_with_content_disposition():
    session = mock_download_response()
    r = session.get()
    r.headers['Content-Disposition'] = " attachment; filename=FILENAME"
    handler = ExecutionHandler(session)
    handler.download('appId', 'fileId', None)

    assert os.path.exists('FILENAME')

    with io.open('FILENAME', 'r+') as f:
        assert f.read() == _FILE_CONTENT
    os.remove('FILENAME')


def test_get_bytes():
    session = mock_download_response()
    handler = ExecutionHandler(session)
    content = handler.get_bytes('appId', 'fileId')

    assert content == _FILE_CONTENT


def test_download_internal_error():
    session = mock_download_response(404)
    handler = ExecutionHandler(session)
    assert_raises(InternalError, handler.download, 'appId', 'fileId', _FILE_PATH)


def test_get_bytes_internal_error():
    session = mock_download_response(404)
    handler = ExecutionHandler(session)
    assert_raises(InternalError, handler.get_bytes, 'appId', 'fileId')


# FILE / GET_FILE_NAME

class File():
    def __init__(self, name):
        self.name = name


def test_get_file_name_positive():
    handler = ExecutionHandler()
    file = File('valid.txt')
    assert handler._get_file_name('somecommand file:valid.txt', file) == file.name


def test_get_file_name_negative():
    handler = ExecutionHandler()
    file = File('/ere/ere/invalid.txt')
    assert handler._get_file_name('somecommand file:invalid.txt', file) == os.path.basename(file.name)
    # assert_raises(ValueError, handler._get_file_name, 'somecommand file:valid.txt', file)


def test_command_get():
    handler = ExecutionHandler()
    set_command_mock(handler, post_res_code=201, get_res_code=200)

    _last_request_id = 'RANDOM_LAST_REQUEST_ID'
    handler._command_get(_last_request_id)

    handler._session.get.assert_called_with(
        handler._urls[ExecutionHandler._KEY_GET] + '/' + _last_request_id + '/stream',
        headers=ANY, allow_redirects=True)


def test_execute_positive():
    """
    Test the scenario when the all 2 requests succeed
    """
    handler = ExecutionHandler(output_factory=TerminalOutputFactory())
    set_command_mock(handler, post_res_code=201, get_res_code=200)
    result = handler.execute('command')
    assert result.is_command_result_available() is True


def test_execute_post_fails():
    """
    Test the scenario when the request (post) in the method 'execute'  fails
    """
    handler = ExecutionHandler(output_factory=TerminalOutputFactory())
    set_command_mock(handler, post_res_code=404, get_res_code=200)
    result = handler.execute('command')
    assert result.is_command_result_available() is False


def test_execute_get_fails():
    """
    Test the scenario when the request (get) in the method 'execute'  fails
    """
    handler = ExecutionHandler(output_factory=TerminalOutputFactory())
    set_command_mock(handler, post_res_code=201, get_res_code=404)
    result = handler.execute('command')
    assert result.is_command_result_available() is False


def test_file_result_get_name():
    """
    Test that FileResult.get_name() returns what is expected in various cases
    """
    test_file_names = [
        ("myfile.txt", "myfile.txt"),
        ("myfile", "myfile"),
        ("/some/path/myfile.txt", "myfile.txt"),
        ("some/path/myfile.txt", "myfile.txt"),
        ("///some/path/myfile.txt", "myfile.txt"),
        ("///myfile.txt", "myfile.txt")
    ]

    for data, expected_output in test_file_names:
        object_under_test = FileResult("", data, MagicMock())
        assert object_under_test.get_name() == expected_output, \
            "expected {0}, got {1}".format(expected_output, object_under_test.get_name())


def test_file_result_delegate_no_path():
    """
    Test that FileResult.download() delegates the implementation to EnmTerminal
    """
    handler = MagicMock()
    object_under_test = FileResult("app", "file", handler)
    object_under_test.download()
    handler.download.assert_called_with('app', 'file', None)


def test_file_result_delegate_with_path():
    """
    Test that FileResult.download() delegates the implementation to EnmTerminal
    """
    terminal = MagicMock()
    terminal.download = MagicMock()
    object_under_test = FileResult("app", "file", terminal)
    object_under_test.download('some/path')
    terminal.download.assert_called_with('app', 'file', 'some/path')


def test_get_bytes_result_delegate():
    """
    Test that FileResult.get_bytes() delegates the implementation to EnmTerminal
    """
    terminal = MagicMock()
    terminal.download = MagicMock()
    object_under_test = FileResult("app", "file", terminal)
    object_under_test.get_bytes()
    terminal.get_bytes.assert_called_with('app', 'file')


def test_command_execute_handler_delegate():
    """
    Test that FileResult.get_bytes() delegates the implementation to EnmTerminal
    """
    _session = MagicMock()
    object_under_test = EnmCommand(_session)
    object_under_test._handler = MagicMock()
    object_under_test._handler.execute.return_value = (NORMAL_RESPONSE, 200, True)
    object_under_test.execute("aaa")
    object_under_test._handler.execute.assert_called_with('aaa', None, 600)


def set_command_mock(handler, post_response_text='', post_res_code='', get_res_code=''):
    response = MagicMock()
    response.status_code = get_res_code
    response.text = generate_json(1, 0, 0, 0)

    post_response = MagicMock()
    post_response.status_code = post_res_code
    post_response.text = post_response_text

    _session = MagicMock()
    _session.post.return_value = post_response
    _session.get.return_value = response
    handler._session = _session


NORMAL_RESPONSE = '{"nonCachableDtos":[],"responseDto":' \
                  '{"dtoType":"ResponseDto","elements":[{"dtoType":"line","value":"1 instance(s)","dtoName":null},' \
                  '{"dtoType":"line","value":"","dtoName":null},{"dtoType":"line","value":null,"dtoName":null},' \
                  '{"dtoType":"line","value":"FDN : MeContext=LTE09ERBS00002","dtoName":null},' \
                  '{"dtoType":"command","value":"cmedit get * MeContext","dtoName":null}],"dtoName":null}}'
