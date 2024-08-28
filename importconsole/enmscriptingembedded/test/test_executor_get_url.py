from enmscripting.private.executionhandler import ExecutionHandler

handler = ExecutionHandler()
REQUEST_ID_QUERY_PARAM = '?_requestId='
REQUEST_ID_DEFAULT_VALUE = 'new'
DEFAULT_REQUEST_POSTFIX = REQUEST_ID_QUERY_PARAM + REQUEST_ID_DEFAULT_VALUE


def test_get_url_relative():
    url = handler._get_request_url('/service', 'something', 'thing')
    assert url == '/service/something/thing' + DEFAULT_REQUEST_POSTFIX


def test_get_url_relative_file_path_param():
    url = handler._get_request_url('/service', 'something', 'thing/1/2/3.log')
    assert url == '/service/something/thing/1/2/3.log' + DEFAULT_REQUEST_POSTFIX


def test_get_url_absolute_gets_trimmed():
    url = handler._get_request_url('/service', '/something', '/thing')
    assert url == '/service/something/thing' + DEFAULT_REQUEST_POSTFIX


def test_get_url_double_leading_slashes_gets_trimmed():
    url = handler._get_request_url('/service', '//something', 'thing')
    assert url == '/service/something/thing' + DEFAULT_REQUEST_POSTFIX


def test_get_url_double_slashes_in_arg_does_not_getting_trimmed():
    url = handler._get_request_url('/service', 'applicationId//absolute/path/to/file')
    assert url == '/service/applicationId//absolute/path/to/file' + DEFAULT_REQUEST_POSTFIX


def test_get_url_request_id():
    handler = ExecutionHandler()
    handler._last_request_id = 'last'
    url = handler._get_request_url('/service', 'something', 'thing')
    assert url == '/service/something/thing' + REQUEST_ID_QUERY_PARAM + 'last'


def test_get_request_url_for_get():
    handler = ExecutionHandler()
    handler._last_request_id = 'last'
    url = handler._get_request_url_for_get('/service', 'last')
    assert url == '/service/last/stream'
