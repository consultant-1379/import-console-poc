# To make Py2 code safer (more like Py3) by preventing implicit relative imports
from __future__ import absolute_import
import socket
import io
import hashlib
import logging
import requests
import datetime
from os.path import expanduser
from os import (path, getenv)
from requests import Session
from requests.exceptions import ConnectionError
from .overrides import overrides
from .logging_util import init_logger
from .retry import (retry, on_fail_sleep)
from ..enmsession import (EnmSession, UnauthenticatedEnmSession)
from ..security.authenticator import (UsernameAndPassword, SsoToken)
from ..exceptions import ConfigurationError
from ..exceptions import SessionTimeoutException
from threading import Lock
try:
    # Python 3
    from http import cookies
    from urllib.parse import (urlencode, urlparse)
    from html.parser import HTMLParser
except ImportError:
    # Python 2
    import Cookie as cookies
    from urllib import urlencode
    from urlparse import urlparse
    from HTMLParser import HTMLParser

"""
enm-client-scripting private module: session

This is a private module and should not be used outside of the client-scripting module.
"""
try:
    requests.packages.urllib3.disable_warnings()
except AttributeError:
    pass  # requests 1.1.0 does not have this feature

_AUTH_COOKIE_KEY = 'iPlanetDirectoryPro'
_ENV_CLIENT_SCRIPTING_VERIFY = 'ENM_CLIENT_SCRIPTING_VERIFY'

logger = logging.getLogger(__name__)


def _open_external_session(url, username=None, password=None):
    """
    Open an external session towards ENM (eg from laptop)
    """
    logger.info('ENM opening session: %s, %s', url, str(username))

    session = __external_session(url)
    enm_session = UnauthenticatedEnmSession(session)

    if username:
        enm_session = enm_session.with_credentials(UsernameAndPassword(username, password))
    logger.info('ENM session is open: [%s][%s][%s]', url, str(username), str(session))

    return enm_session


def _open_internal_session(url=None, username=None, password=None):
    """
    Open an internal session towards ENM REST interface (eg on scripting VM)
    """
    logger.info('ENM opening internal session')

    session = InternalSession()

    if url is not None or username is not None or password is not None:
        logger.warn('On scripting VM, URL and credentials parameters will be ignored')

    session.open_session(SsoToken.from_file(session.cookie_path()))

    class InternalEnmSession(EnmSession, UnauthenticatedEnmSession):

        def __init__(self, session):
            super(InternalEnmSession, self).__init__(session)

        def with_credentials(self, authenticator):
            logger.warn('On scripting VM, URL and credentials parameters will be ignored')
            return self

    enm_session = InternalEnmSession(session)
    logger.info('ENM session is open: [%s]', session.url())
    return enm_session


def _close_session(enm_session):
    enm_session._session.close_session()


def __external_session(url):
    return ExternalSession(url)


def _check_for_warning_header(response):
    headers = response.headers
    for header_key in headers:
        if header_key.lower() == 'warning':
            if headers[header_key].startswith('299'):
                logger.warn('Warning: ' + headers[header_key])


def _output_content_and_headers_for_error(response):
    logger.debug("Accept response: Server response code is [%i], returning False", response.status_code)
    logger.error("Accept response: Server response content is " + str(response.content))
    logger.error("Accept response: Server response headers are " + str(response.headers))


def _raise_session_timeout_exception():
    logger.debug("Session timeout error: " +
                 "The script has failed to run at [%s] as the session timeout has expired.",
                 datetime.datetime.utcnow().isoformat())
    raise SessionTimeoutException('Session timeout error: ' +
                                  'The script has failed to run at [%s] as the session timeout has expired.'
                                  % datetime.datetime.utcnow().isoformat())


class ExternalSession(Session):
    """
    Session that uses the ENM login / logout endpoints to authenticate
    """

    _AUTH_ERROR_CODE = 'x-autherrorcode'
    _AUTH_OK = '0'
    _RESPONSE_COOKIE_KEY = 'set-cookie'

    _RETRY_ERROR_CODES_POST = (400, 404, 405, 406, 415, 501, 502, 503, 504)

    # Requests error message
    _ERROR_BAD_STATUS_LINE = '(\'Connection aborted.\', BadStatusLine(\"\'\'\",))'

    def __init__(self, url=None):
        super(ExternalSession, self).__init__()
        self._url = url
        self._request_lock = Lock()
        init_logger()  # Logger has to be initialized before the first WARN/ERROR log entry
        self._server_verify()
        self._authenticator = None

    def url(self):
        return self._url

    def _server_verify(self):
        verify_string = getenv(_ENV_CLIENT_SCRIPTING_VERIFY, 'False')
        if 'false' == verify_string.lower():
            self._verify = False
        elif 'true' == verify_string.lower():
            self._verify = True
        elif path.isfile(verify_string):
            self._verify = verify_string
        else:
            raise ConfigurationError('Invalid option for %s [%s]' % (_ENV_CLIENT_SCRIPTING_VERIFY, verify_string))
        logger.debug('Certificate verification is [%s]', self._verify)

    def open_session(self, authenticator):
        self._authenticator = authenticator
        if authenticator:
            authenticator.authenticate(self)

    def close_session(self):
        logger.debug('Closing session: ' + str(self))
        if self._authenticator:
            self._authenticator.logout(self)
        self.cookies.clear_session_cookies()
        self.close()
        logger.debug('Session is closed: ' + str(self))

    def authenticator(self):
        return self._authenticator

    def _accept_response_post(response):
        if isinstance(response, requests.exceptions.ConnectionError):
            if str(response) == ExternalSession._ERROR_BAD_STATUS_LINE:
                logger.debug("Accept response: Connection error occurred [%s], returning False", str(response))
                return False
        elif isinstance(response, requests.models.Response):
            _check_for_warning_header(response)
            if response.status_code in ExternalSession._RETRY_ERROR_CODES_POST:
                _output_content_and_headers_for_error(response)
                return False
            elif response.status_code == 401:
                _raise_session_timeout_exception()
        return True

    def _accept_response(response):
        if isinstance(response, Exception):
            logger.debug("Accept response: Connection error occurred [%s], returning False", str(response))
            return False
        elif isinstance(response, requests.models.Response):
            _check_for_warning_header(response)
            if response.status_code >= 400:
                if response.status_code == 401:
                    _raise_session_timeout_exception()
                else:
                    _output_content_and_headers_for_error(response)
                    return False
        return True

    @overrides
    @retry(attempts=5, accept_func=_accept_response_post, on_fail_func=on_fail_sleep)
    def post(self, url, data=None, **kwargs):
        logger.debug('ExternalSession POST called [%s]', url)
        if 'verify' not in kwargs:
            kwargs['verify'] = self._verify
        with self._request_lock:
            return super(ExternalSession, self).post(url, data=data, **kwargs)

    @overrides
    @retry(attempts=5, accept_func=_accept_response, on_fail_func=on_fail_sleep)
    def get(self, url, **kwargs):
        logger.debug('InternalSession GET called [%s]', url)
        if 'verify' not in kwargs:
            kwargs['verify'] = self._verify
        return super(ExternalSession, self).get(url, **kwargs)

    @overrides
    @retry(attempts=5, accept_func=_accept_response, on_fail_func=on_fail_sleep)
    def head(self, url, **kwargs):
        logger.debug('InternalSession HEAD called [%s]', url)
        if 'verify' not in kwargs:
            kwargs['verify'] = self._verify
        return super(ExternalSession, self).head(url, **kwargs)


class InternalSession(ExternalSession):
    """
    Session that uses cookie file for authentication
    """

    _HA_PROXY_LOOKUP_NAME = 'haproxy'
    _COOKIE_FILE = '.enm_login'
    _COOKIE_PATH = path.join(expanduser("~"), _COOKIE_FILE)
    _HTTP_REDIRECT = 302

    def __init__(self):
        super(InternalSession, self).__init__()
        self._set_url()
        self._server_verify()

    def cookie_path(self):
        return self._COOKIE_PATH

    @overrides
    def _server_verify(self):
        self._verify = False
        if getenv(_ENV_CLIENT_SCRIPTING_VERIFY) is not None:
            logger.warn('Certificate verification [%s] will be set to default [%s]',
                        getenv(_ENV_CLIENT_SCRIPTING_VERIFY), self._verify)

    def _accept_response_redirect(result):
        if isinstance(result, requests.models.Response):
            if result.status_code == InternalSession._HTTP_REDIRECT:
                logger.debug("Accept response: Server response is [%i], returning False", result.status_code)
                return False
        return True

    def _on_fail_reload_cookie(result, return_object, *args, **kwargs):
        logger.debug("Reloading cookie and retrying request")
        self = args[0]  # args contains the function arguments, first is always 'self'
        self._re_authenticate()

    @overrides
    @retry(attempts=2, accept_func=_accept_response_redirect, on_fail_func=_on_fail_reload_cookie)
    def post(self, url, data=None, **kwargs):
        logger.debug('InternalSession POST called [%s]', url)
        return super(InternalSession, self).post(url, data=data, **kwargs)

    @overrides
    @retry(attempts=2, accept_func=_accept_response_redirect, on_fail_func=_on_fail_reload_cookie)
    def get(self, url, **kwargs):
        logger.debug('InternalSession GET called [%s]', url)
        return super(InternalSession, self).get(url, **kwargs)

    @overrides
    @retry(attempts=2, accept_func=_accept_response_redirect, on_fail_func=_on_fail_reload_cookie)
    def head(self, url, **kwargs):
        logger.debug('InternalSession HEAD called [%s]', url)
        return super(InternalSession, self).head(url, **kwargs)

    @overrides
    def open_session(self, authenticator):
        try:
            super(InternalSession, self).open_session(authenticator)
        except ValueError:
            logger.warn('Failed to open cookie file, returning')

    def _re_authenticate(self):
        if self._authenticator:
            try:
                self._authenticator.authenticate(self)
            except ValueError:
                logger.warn('Failed to open cookie file, returning')

    def _set_url(self):
        """
        Sets the URL

        Looks up HA proxy IP, then does a GET to find out where the request gets redirected.
        Example:
            ha_url = 'https://1.2.3.4'
            redirected_url = 'https://my.enm.host.com:443/login/?goto=https%3A%2F%2Fmy.enm.host.com%3A443%2F'
            url = 'https://my.enm.host.com'
        """
        logger.debug('Setting the URL of ENM')
        ha_url = ''.join(('https://', socket.gethostbyname(self._HA_PROXY_LOOKUP_NAME)))
        # verify=False is fine, because server cert is issued to domain name, and it gets validated later
        logger.debug('Getting the redirected url from [%s]', ha_url)
        redirected_url = self.get(ha_url, verify=False).url
        parsed = urlparse(redirected_url)
        self._url = ''.join(('https://', parsed.hostname))
        logger.debug('ENM URL is set [%s]', self.url())
