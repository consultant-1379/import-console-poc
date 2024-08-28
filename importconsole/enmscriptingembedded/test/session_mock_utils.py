import requests
import responses
from posixpath import join as urljoin
from enmscripting.private.session import (ExternalSession, _AUTH_COOKIE_KEY)


login_url = 'https://localhost'
_session_cookie = 'testCookie'
# Original session init
_session_init_orig = requests.Session.__init__


def setup_session_mock():
    requests.Session.__init__ = _mock_session_init


def teardown_session_mock():
    requests.Session.__init__ = _session_init_orig


def mock_login_response(auth_cookie='testCookie', xautherror_code="0", body=''):
    if xautherror_code is not None:
        headers = {'x-autherrorcode': xautherror_code}
    else:
        headers = None
    responses.add(responses.POST, urljoin(login_url, 'login'), adding_headers=headers, body=body)

    global _session_cookie
    _session_cookie = auth_cookie


def mock_logout_response():
    responses.add(responses.GET, urljoin(login_url, 'logout'))


def _mock_session_init(self):
    """
    This method will get called each time a new instance of Session (InternalSession / ExternalSession) is created
    """
    # Calling original init
    _session_init_orig(self)
    # Altering the behaviour using mocks
    if _session_cookie is not None:
        self.cookies[_AUTH_COOKIE_KEY] = _session_cookie
    # print('Auth cookie is set [%s]' % _session_cookie)
