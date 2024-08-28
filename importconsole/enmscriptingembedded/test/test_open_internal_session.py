import io
import os
import enmscripting
import logging
from nose import with_setup
from nose.tools import assert_raises
from responses import activate as mock_responses
from enmscripting.private.session import (InternalSession, ExternalSession)
from enmscripting.private.session import _open_internal_session as open
from enmscripting.enmscripting import close
from ..exceptions import SessionTimeoutException
from .session_mock_utils import *
from enmscripting.security.authenticator import (UsernameAndPassword, SsoToken)
from enmscripting.enmsession import (UnauthenticatedEnmSession)

logging.basicConfig()
logging.getLogger().setLevel(level=logging.DEBUG)

_TEST_COOKIE_PATH = '.enm_login'
_TEST_FAKE_COOKIE_PATH = '.fakeCookieFile'
_TEST_COOKIE_VALUE = 'testCookie'
_DEFAULT_COOKIE_VALUE = ''
_URL = 'https://127.0.0.1'


def setup_func():
    enmscripting.private.session.InternalSession._HA_PROXY_LOOKUP_NAME = 'localhost'
    _write_cookie_file(_TEST_COOKIE_VALUE)
    _set_cookie_path(_TEST_COOKIE_PATH)
    responses.add(responses.GET, _URL)


def teardown_func():
    os.remove(_TEST_COOKIE_PATH)


def assert_nr_calls(expected):
    assert len(responses.calls) == expected, \
        "Number of calls was [%s] but expected [%i] " % (len(responses.calls), expected)


@mock_responses
@with_setup(setup_func, teardown_func)
def test_open():
    session = open()._session

    assert session
    assert isinstance(session, InternalSession)


@mock_responses
@with_setup(setup_func, teardown_func)
def test_open_with_params_ignored():
    session = open('fake_url', 'user', 'pass')._session

    assert session
    assert isinstance(session, InternalSession)
    assert session.url() == _URL
    assert isinstance(session.authenticator(), SsoToken)
    assert session.authenticator().token() == _TEST_COOKIE_VALUE


@mock_responses
@with_setup(setup_func, teardown_func)
def test_open_with_username_authenticator_and_params_are_ignored():
    not_authenticated_session = open('fake_url')

    assert not_authenticated_session
    assert isinstance(not_authenticated_session, UnauthenticatedEnmSession)
    session = not_authenticated_session.with_credentials(UsernameAndPassword('user', 'pass'))._session

    assert session
    assert isinstance(session, InternalSession)
    assert session.url() == _URL
    assert isinstance(session.authenticator(), SsoToken)
    assert session.authenticator().token() == _TEST_COOKIE_VALUE


@mock_responses
@with_setup(setup_func, teardown_func)
def test_open_with_ssotoken_authenticator_and_params_are_ignored():
    not_authenticated_session = open('fake_url')

    assert not_authenticated_session
    assert isinstance(not_authenticated_session, UnauthenticatedEnmSession)
    session = not_authenticated_session.with_credentials(SsoToken.from_file('fake/token/file/path'))._session

    assert session
    assert isinstance(session, InternalSession)
    assert session.url() == _URL
    assert isinstance(session.authenticator(), SsoToken)
    assert session.authenticator().token() == _TEST_COOKIE_VALUE


@mock_responses
@with_setup(setup_func, teardown_func)
def test_close_cookie_deleted():
    enm_session = open()
    int_session = enm_session._session

    assert int_session.authenticator().token() == _TEST_COOKIE_VALUE

    close(enm_session)
    assert int_session.authenticator().token() == _DEFAULT_COOKIE_VALUE


@mock_responses
@with_setup(setup_func, teardown_func)
def test_open_cookie_read():
    session = open()._session
    assert session.authenticator().token() is not None
    assert session.authenticator().token() == _TEST_COOKIE_VALUE


@mock_responses
@with_setup(setup_func, teardown_func)
def test_open_cookie_not_present():
    _set_cookie_path(_TEST_FAKE_COOKIE_PATH)
    session = open()._session
    assert session.authenticator().token() is not None
    assert session.authenticator().token() == _DEFAULT_COOKIE_VALUE


@mock_responses
@with_setup(setup_func, teardown_func)
def test_execute_reload_no_change():
    session = open()._session
    # After open
    assert session.authenticator().token() == _TEST_COOKIE_VALUE
    cookie_hash = session.authenticator()._auth_cookie_hash()
    assert cookie_hash is not None

    responses.add(responses.POST, _URL, status=302)
    session.post(session.url())

    # After execute
    assert cookie_hash == session.authenticator()._auth_cookie_hash()
    assert session.authenticator().token() == _TEST_COOKIE_VALUE
    assert len(responses.calls) == 3  # open + post + retry


@mock_responses
@with_setup(setup_func, teardown_func)
def test_execute_reload_cookie_changed():
    session = open()._session
    # After open
    assert session.authenticator().token() == _TEST_COOKIE_VALUE
    cookie_hash = session.authenticator()._auth_cookie_hash()
    assert cookie_hash is not None

    # New cookie file present
    _write_cookie_file('new cookie value')
    responses.add(responses.POST, _URL, status=302)
    session.post(session.url())

    # After execute
    assert cookie_hash != session.authenticator()._auth_cookie_hash()
    assert session.authenticator().token() == 'new cookie value'
    assert len(responses.calls) == 3  # open + post + retry


# Postive post test cases

@mock_responses
@with_setup(setup_func, teardown_func)
def test_post_positive():
    session = open()._session
    responses.add(responses.POST, _URL, status=200)
    result = session.post(session.url())
    assert result.status_code == 200
    assert_nr_calls(2)  # open + post


@mock_responses
@with_setup(setup_func, teardown_func)
def test_post_positive_with_warning():
    session = open()._session
    responses.add(responses.POST, _URL, status=200, adding_headers={'warning': '299 - My warning'})
    result = session.post(session.url())
    assert result.status_code == 200
    assert_nr_calls(2)  # open + post


@mock_responses
@with_setup(setup_func, teardown_func)
def test_post_positive_with_warning_no_display():
    session = open()._session
    responses.add(responses.POST, _URL, status=200, adding_headers={'warning': '300 - My warning'})
    result = session.post(session.url())
    assert result.status_code == 200
    assert_nr_calls(2)  # open + post


# Negative post test cases

@mock_responses
@with_setup(setup_func, teardown_func)
def test_post_connection_error():
    session = open()._session

    # Throws connection error with bad status line
    conn_error = requests.exceptions.ConnectionError(ExternalSession._ERROR_BAD_STATUS_LINE)
    responses.add(responses.POST, _URL, body=conn_error)

    assert_raises(requests.exceptions.ConnectionError, session.post, session.url())
    assert_nr_calls(6)  # open + post (ConnectionError) + 4 retry


@mock_responses
@with_setup(setup_func, teardown_func)
def test_post_exception_no_retry():
    session = open()._session
    value_error = ValueError("Something went wrong")
    responses.add(responses.POST, _URL, body=value_error)
    assert_raises(ValueError, session.post, session.url())
    assert_nr_calls(2)  # open + post 1 attempt (no retry)


@mock_responses
@with_setup(setup_func, teardown_func)
def test_head_exception():
    session = open()._session
    value_error = ValueError("Something went wrong")
    responses.add(responses.HEAD, _URL, body=value_error)

    assert_raises(ValueError, session.head, session.url())
    assert_nr_calls(6)  # open + post 5 attempts


@mock_responses
@with_setup(setup_func, teardown_func)
def test_post_503_response_retry():
    session = open()._session
    responses.add(responses.POST, _URL, status=503)
    result = session.post(session.url())
    assert result.status_code == 503
    assert_nr_calls(6)  # open + post 5 attempts


@mock_responses
@with_setup(setup_func, teardown_func)
def test_post_504_response_retry():
    session = open()._session
    responses.add(responses.POST, _URL, status=504)
    result = session.post(session.url())
    assert result.status_code == 504
    assert_nr_calls(6)  # open + post 5 attempts


@mock_responses
@with_setup(setup_func, teardown_func)
def test_post_505_response_no_retry():
    session = open()._session
    responses.add(responses.POST, _URL, status=505)
    result = session.post(session.url())
    assert result.status_code == 505
    assert_nr_calls(2)  # open + post 1 attempt (no retry)


@mock_responses
@with_setup(setup_func, teardown_func)
def test_head_505_response_retry():
    session = open()._session
    responses.add(responses.HEAD, _URL, status=505)
    result = session.head(session.url())
    assert result.status_code == 505
    assert_nr_calls(6)  # open + post 5 attempts


@mock_responses
@with_setup(setup_func, teardown_func)
def test_get_401_raise_exception():
    session = open()._session
    responses.add(responses.GET, _URL + 'test_get_401', status=401)
    assert_raises(SessionTimeoutException, session.get, session.url() + 'test_get_401')


@mock_responses
@with_setup(setup_func, teardown_func)
def test_post_401_raise_exception():
    session = open()._session
    responses.add(responses.POST, _URL + 'test_post_401', status=401)
    assert_raises(SessionTimeoutException, session.post, session.url() + 'test_post_401')


@mock_responses
@with_setup(setup_func, teardown_func)
def test_head_401_raise_exception():
    session = open()._session
    responses.add(responses.HEAD, _URL + 'test_head_401', status=401)
    assert_raises(SessionTimeoutException, session.head, session.url() + 'test_head_401')


@mock_responses
@with_setup(setup_func, teardown_func)
def test_get_reload_cookie_changed():
    session = open()._session
    # After open
    assert session.authenticator().token() == _TEST_COOKIE_VALUE
    cookie_hash = session.authenticator()._auth_cookie_hash()
    assert cookie_hash is not None

    # New cookie file present
    _write_cookie_file('new cookie value')
    responses.reset()
    responses.add(responses.GET, _URL, status=302)
    session.get(session.url())

    # After execute
    assert cookie_hash != session.authenticator()._auth_cookie_hash()
    assert session.authenticator().token() == 'new cookie value'
    assert len(responses.calls) == 2  # get + retry


@mock_responses
@with_setup(setup_func, teardown_func)
def test_head_reload_cookie_changed():
    session = open()._session
    # After open
    assert session.authenticator().token() == _TEST_COOKIE_VALUE
    cookie_hash = session.authenticator()._auth_cookie_hash()
    assert cookie_hash is not None

    # New cookie file present
    _write_cookie_file('new cookie value')
    responses.add(responses.HEAD, _URL, status=302)
    session.head(session.url())

    # After execute
    assert cookie_hash != session.authenticator()._auth_cookie_hash()
    assert session.authenticator().token() == 'new cookie value'
    assert len(responses.calls) == 3  # open + get + retry


def _set_cookie_path(path):
    enmscripting.private.session.InternalSession._COOKIE_PATH = path


def _write_cookie_file(cookie_value):
    with io.open(_TEST_COOKIE_PATH, "wb+") as f:
        f.write(cookie_value.encode('utf-8'))
