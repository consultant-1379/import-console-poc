import logging
from responses import activate as mock_responses
from nose import (with_setup)
from nose.tools import (assert_raises)
import enmscripting
from enmscripting.private.session import (ExternalSession, _AUTH_COOKIE_KEY)
from enmscripting.security.authenticator import (LoginResponseParser, UsernameAndPassword, SsoToken, _AUTH_COOKIE_KEY)
from enmscripting.enmsession import (UnauthenticatedEnmSession)
from .session_mock_utils import *
try:
    from unittest.mock import MagicMock, patch
except ImportError:
    from mock import MagicMock, patch

logging.basicConfig()
logging.getLogger().setLevel(level=logging.DEBUG)


def mock_open(read_data=''):
    file_handler = MagicMock()
    file_handler.__enter__ = MagicMock(return_value=file_handler)
    file_handler.readline = MagicMock(return_value=read_data)
    open_function = MagicMock(return_value=file_handler)
    return open_function


@mock_responses
@with_setup(setup_session_mock, teardown_session_mock)
def test_open():
    mock_login_response('testCookie', '0')
    session = enmscripting.open(login_url, 'username', 'pass')._session

    assert session
    assert isinstance(session, ExternalSession)


@mock_responses
@with_setup(setup_session_mock, teardown_session_mock)
def test_open_with_username_and_password_authenticator():
    mock_login_response('testCookie', '0')
    not_authenticated_session = enmscripting.open(login_url)

    assert not_authenticated_session
    assert isinstance(not_authenticated_session, UnauthenticatedEnmSession)

    session = not_authenticated_session.with_credentials(UsernameAndPassword('username', 'pass'))._session

    assert session
    assert isinstance(session, ExternalSession)


@patch('io.open', mock_open(read_data="the-saved-token-value"))
def test_open_with_ssotoken_authenticator():
    not_authenticated_session = enmscripting.open(login_url)

    assert not_authenticated_session
    assert isinstance(not_authenticated_session, UnauthenticatedEnmSession)

    session = not_authenticated_session.with_credentials(SsoToken.from_file('token/file/path'))._session

    assert session
    assert isinstance(session, ExternalSession)
    assert session.cookies[_AUTH_COOKIE_KEY] == "the-saved-token-value"
    assert session.authenticator().token() == "the-saved-token-value"


@mock_responses
@with_setup(setup_session_mock, teardown_session_mock)
def test_open_authentication_failed_auth_code_not_0():
    mock_login_response('testCookie', '-1')
    assert_raises(ValueError, enmscripting.open, login_url, 'username', 'pass')


@mock_responses
@with_setup(setup_session_mock, teardown_session_mock)
def test_open_authentication_failed_auth_code_minus_2():
    mock_login_response('testCookie', '-2')
    assert_raises(ValueError, enmscripting.open, login_url, 'username', 'pass')


@mock_responses
@with_setup(setup_session_mock, teardown_session_mock)
def test_open_no_cookie():
    mock_login_response(None, '0')
    assert_raises(ValueError, enmscripting.open, login_url, 'username', 'pass')


@mock_responses
@with_setup(setup_session_mock, teardown_session_mock)
def test_open_authentication_failed_no_auth_code():
    mock_login_response('testCookie', None)
    assert_raises(ValueError, enmscripting.open, login_url, 'username', 'pass')


@mock_responses
@with_setup(setup_session_mock, teardown_session_mock)
def test_close():

    mock_login_response()
    enm_session = enmscripting.open(login_url, 'username', 'pass')

    session = enm_session._session
    assert len(session.cookies) is 1

    mock_logout_response()
    enmscripting.close(enm_session)
    assert len(session.cookies) is 0


@mock_responses
@with_setup(setup_session_mock, teardown_session_mock)
def test_open_password_reset_required():
    mock_login_response('testCookie', None, '<html><head id="oasis_login">'
                                            '<script language="JavaScript" type="text/javascript">'
                                            '<!-- function redirectToEnmPasswordChange() {} --></script>'
                                            '</head><body id="null" onload="redirectToEnmPasswordChange()" /></html>')
    try:
        enmscripting.open(login_url, 'username', 'pass')
        assert False, 'Open should throw ValueError, when user is required to change password'
    except ValueError as e:
        assert 'password change required' in str(e), 'Incorrect error message [%s]' % str(e)


def test_login_response_redirect_true():
    assert LoginResponseParser('<html><body id="null" onload="redirectToEnmPasswordChange()" /><some></some>'
                               '</html>').password_change_redirect() is True


def test_login_response_redirect_false():
    assert LoginResponseParser('<html><body id="null" onload="someMethod()">redirectToEnmPasswordChange</body>'
                               '</html>').password_change_redirect() is False
