import logging
import os
import socket
import io
from requests import Session, ConnectionError, Timeout
from posixpath import join as urljoin
from ssl import SSLError

try:
    # Python 3
    from html.parser import HTMLParser
    from urllib.parse import (urlencode, urlparse)
except ImportError:
    # Python 2
    from urllib import urlencode
    from urlparse import urlparse
    from HTMLParser import HTMLParser

try:
    from requests.packages.urllib3 import disable_warnings
    disable_warnings()
except AttributeError:
    pass  # requests 1.1.0 does not have this feature

logger = logging.getLogger(__name__)

_CONNECTION_TIMEOUT_SECONDS = 30


class NbiSession:
    """
    Class that creates an HTTP authenticated session towards ENM to send ImportScriptingRequests
    to CM Import NBI
    """
    _AUTH_COOKIE_KEY = 'iPlanetDirectoryPro'
    _AUTH_ERROR_CODE = 'x-autherrorcode'
    _AUTH_OK = '0'
    _HEADER_DEFAULT = {'X-Requested-With': 'XMLHttpRequest', 'Content-type': 'application/json',
                       'Accept': 'application/json, application/hal+json', 'Accept-Encoding': ', '.join(('gzip', 'deflate', 'sdch'))}
    _HA_PROXY_LOOKUP_NAME = 'haproxy'
    _COOKIE_FILE = '.enm_login'
    _COOKIE_PATH = os.path.join(os.path.expanduser("~"), _COOKIE_FILE)

    def __init__(self, service_uri, host=None, username=None, password=None):
        """
        Class constructor
        :param host: base protocol+host of ENM. Eg.: https://enm.athtem.eei.ericsson.se
        :param username: Username to be used to authenticate on ENM
        :param password: User's password
        :param service_uri: The NBI service URI. Eg.: /import
        """
        self._session = Session()
        self._username = username
        self._password = password
        self._host = host if host else self._try_discover_enm_host(self._session)
        self._verify = False
        self._nbi_url = urljoin(self._host, service_uri)
        self._session_open = False
        self._use_sso = (not username)

    def username(self):
        return self._username

    def password(self):
        return self._password

    def host(self):
        return self._host

    def open_session(self):
        """
        Open session and authenticate towards ENM
        :return: void
        """
        try:
            if self._use_sso:
                logger.debug('[ImportScriptingSolution] Opening session towards ENM [%s] with SSO.', self._host)
                self._load_sso_cookie()
            else:
                logger.debug('[ImportScriptingSolution] Opening session towards ENM [%s] and authenticating user [%s]',
                             self._host, self._username)
                self._login()
            self._session_open = True
        except (ConnectionError, Timeout, SSLError) as e:
            raise NbiConnectionException(e)

    def close_session(self):
        """
        Close connection and logout from ENM
        :return: void
        """
        logger.debug('[ImportScriptingSolution] Closing session: ' + str(self))
        if not self._use_sso:
            self._session.get(urljoin(self._host, 'logout'), verify=self._verify, allow_redirects=True,
                              timeout=_CONNECTION_TIMEOUT_SECONDS)
        self._session.cookies.clear_session_cookies()
        self._session.close()
        self._session_open = False
        logger.debug('[ImportScriptingSolution] Session is closed: ' + str(self))

    def get(self, path='', parameters={}, headers={}):
        return self.fetch_request(self.get_method, path=path, parameters=parameters, headers=headers)

    def post(self, path='', request_body=None, parameters={}, headers={}, files=None):
        return self.fetch_request(self.post_method, path=path, parameters=parameters, headers=headers, request_body=request_body, files=files)

    def put(self, path='', request_body=None, parameters={}, headers={}, files=None):
        return self.fetch_request(self.put_method, path=path, parameters=parameters, headers=headers, request_body=request_body, files=files)

    def get_method(self, *args, **kwargs):
        return self._session.get(*args, **kwargs)

    def post_method(self, *args, **kwargs):
        return self._session.post(*args, **kwargs)

    def put_method(self, *args, **kwargs):
        return self._session.put(*args, **kwargs)

    def fetch_request(self, *args, **kwargs):
        return self.send_request(*args, **kwargs).json()

    def send_request(self, method, path='', request_body=None, files=None, parameters={}, headers={}, stream=False):
        """
        Sends the provided http request
        :param method: one of *_method functions
        :param path: resource URI to send request to
        :param request_body: request data to be sent
        :param parameters: map of query string parameters
        :param headers: optional headers to be sent
        :return: the server response as json object
        """
        if not self._session_open:
            raise Exception('Invalid state, Session must be opened before sending requests.')

        try:
            all_headers = self._HEADER_DEFAULT.copy()
            if files:
                del all_headers['Content-type']
            all_headers.update(headers)
            response = method(self.to_full_url(path),
                                          data=request_body,
                                          files=files,
                                          params=parameters,
                                          headers=all_headers,
                                          verify=self._verify,
                                          allow_redirects=False,
                                          timeout=_CONNECTION_TIMEOUT_SECONDS,
                                          stream=stream)
        except (ConnectionError, Timeout, SSLError) as e:
            logger.exception('Connection error: %s', e)
            raise NbiConnectionException(e)

        if response.status_code not in (200, 201, 202):
            logger.debug("[ImportScriptingSolution] Response status code was: %d", response.status_code)
            text = response.text
            try:
                data = response.json()
                text = None
            except:
                data = None

            logger.debug('data %s and text %s ', str(data), str(text))

            if response.status_code == 401:
                raise NbiAccessNotAllowedException(response.status_code, response_text=text, json=data)
            elif response.status_code == 400:
                raise NbiBadRequestException(response.status_code, response_text=text, json=data)
            elif response.status_code == 204:
                raise NbiNoContentException(response.status_code, response_text=text, json=data)
            elif response.status_code == 404:
                raise NbiServiceUnavailableException(response.status_code, response_text=text, json=data)
            elif response.status_code == 302 and self._use_sso:
                self._load_sso_cookie()
                raise AuthenticationTokenExpiredException(response.status_code, response_text=text, json=data)
            else:
                raise NbiRequestException(response.status_code, response_text=text, json=data)

        return response

    # def _send_nbi_request(self, management_request, test):
    #     attributes = management_request.get_attributes().copy()
    #     attributes['executionMode'] = 'EXECUTE' if not test else 'TEST'
    #     attributes['responseLevel'] = 'HIGH'
    #     # attributes['handoverType'] = 'LTE_WCDMA'
    #     request_body = json.dumps(attributes)
    #     logger.debug("[CellMngtNbiSession] Sending request: %s", request_body)
    #     try:
    #         response = self._session.post(self._nbi_url, data=request_body, headers=self._HEADER_DEFAULT,
    #                                       verify=self._verify, allow_redirects=False,
    #                                       timeout=_CONNECTION_TIMEOUT_SECONDS)
    #     except (ConnectionError, Timeout, SSLError) as e:
    #         raise NbiConnectionException(e)
    #
    #     logger.debug("[CellMngtNbiSession] Response was: %s", response.text)
    #     if response.status_code not in (200, 201):
    #         logger.debug("[CellMngtNbiSession] Response status code was: %d", response.status_code)
    #         text = response.text
    #         try:
    #             data = response.json()
    #             text = None
    #         except:
    #             data = None
    #
    #         if response.status_code == 401:
    #             raise NbiAccessNotAllowedException(response.status_code, response_text=text, json=data)
    #         elif response.status_code == 404:
    #             raise NbiServiceUnavailableException(response.status_code, response_text=text, json=data)
    #         elif response.status_code == 302 and self._use_sso:
    #             self._load_sso_cookie()
    #             raise AuthenticationTokenExpiredException(response.status_code, response_text=text, json=data)
    #         else:
    #             raise NbiRequestException(response.status_code, response_text=text, json=data)
    #
    #     return response

    def _login(self):
        response = self._session.post(urljoin(self._host, 'login'),
                                      data={'IDToken1': self._username, 'IDToken2': self._password},
                                      verify=self._verify, allow_redirects=False, timeout=_CONNECTION_TIMEOUT_SECONDS)
        if self._AUTH_ERROR_CODE not in response.headers:
            if LoginResponseParser(response.text).password_change_redirect():
                # Redirect detected
                logger.error('Invalid login, password change required for user [%s]. '
                             'Please change it via ENM login page', self._username)
                raise ValueError('Invalid login, password change required for user [%s]. '
                                 'Please change it via ENM login page' % self._username)
            else:
                # Not ENM server
                logger.error('Failed to open session. Please make sure the URL [%s] is a valid ENM URL', self._host)
                raise ValueError(
                    'Failed to open session. Please make sure the URL [%s] is a valid ENM URL' % self._host)
        elif response.headers[self._AUTH_ERROR_CODE] is not self._AUTH_OK or \
                        self._AUTH_COOKIE_KEY not in self._session.cookies.keys():
            # Authentication failed
            logger.error('Invalid login, credentials are invalid for user [%s]', self._username)
            raise ValueError('Invalid login, credentials are invalid for user [%s]' % self._username)
        logger.debug("[ImportScriptingSolution] User [%s] is logged in.", self._username)

    def _load_sso_cookie(self):
        logger.debug('[ImportScriptingSolution] Loading cookie from file [%s]', self._COOKIE_PATH)
        try:
            with io.open(self._COOKIE_PATH, 'r') as cookie:
                new_cookie = cookie.readline().strip()
        except (OSError, IOError) as e:
            logger.warn('Failed to open cookie file [%s], returning', self._COOKIE_PATH)
            logger.exception(e)
            raise MissingCredentialsException(999)

        self._session.cookies[self._AUTH_COOKIE_KEY] = new_cookie
        logger.debug('New authentication cookie is set')

    def _try_discover_enm_host(self, session):
        """
        Tries do discover ENM's domain url. It only works from scripting VM.

        Looks up HA proxy IP, then does a GET to find out where the request gets redirected.
        Example:
            ha_url = 'https://1.2.3.4'
            redirected_url = 'https://my.enm.host.com:443/login/?goto=https%3A%2F%2Fmy.enm.host.com%3A443%2F'
            url = 'https://my.enm.host.com'
        """
        try:
            logger.debug('Looking for ENM\' URL')
            ha_url = ''.join(('https://', socket.gethostbyname(self._HA_PROXY_LOOKUP_NAME)))
            # verify=False is fine, because server cert is issued to domain name, and it gets validated later
            logger.debug('Getting the redirected url from [%s]', ha_url)
            response = session.get(ha_url, verify=False, timeout=_CONNECTION_TIMEOUT_SECONDS)
            response.raise_for_status()
            redirected_url = response.url
            parsed = urlparse(redirected_url)
            enm_url = ''.join(('https://', parsed.hostname))
            logger.debug('ENM URL is [%s]', enm_url)
            return enm_url
        except Exception as e:
            logger.error('Failed to resolver ENM\'s host name')
            logger.exception(e)
            raise NbiUnknownServiceHostException()

    def to_full_url(self, path):
        if path.startswith('http'):
            return path
        elif path.startswith('/'):
            return urljoin(self._host, path[1:])
        else:
            return urljoin(self._nbi_url, path)


class NbiRequestException(Exception):
    def __init__(self, status_code, response_text='', json=None, *args, **kwargs):
        super(NbiRequestException, self).__init__(*args, **kwargs)
        self.status_code = status_code
        self.response_text = response_text
        self.json = json

    def __str__(self):
        return 'Nbi request failed with response code: ' + str(self.status_code)


class AuthenticationTokenExpiredException(NbiRequestException):
    def __init__(self, status_code, response_text='', json=None, *args, **kwargs):
        super(AuthenticationTokenExpiredException, self).__init__(status_code, response_text, json, *args, **kwargs)

    def __str__(self):
        return 'Server responded with %d, it seems that your authentication session has expired. Please login again.' \
               % self.status_code


class MissingCredentialsException(NbiRequestException):
    def __init__(self, status_code, response_text='', json=None, *args, **kwargs):
        super(MissingCredentialsException, self).__init__(status_code, response_text, json, *args, **kwargs)

    def __str__(self):
        return 'Missing credentials, can\'t authenticate.'


class NbiNoContentException(NbiRequestException):
    def __init__(self, status_code, response_text='', json=None, *args, **kwargs):
        super(NbiNoContentException, self).__init__(status_code, response_text, json, *args, **kwargs)

    def __str__(self):
        return 'Nothing found.'


class NbiAccessNotAllowedException(NbiRequestException):
    def __init__(self, status_code, response_text='', json=None, *args, **kwargs):
        super(NbiAccessNotAllowedException, self).__init__(status_code, response_text, json, *args, **kwargs)

    def __str__(self):
        return 'Security Violation. Access not allowed.'


class NbiServiceUnavailableException(NbiRequestException):
    def __init__(self, status_code, response_text='', json=None, *args, **kwargs):
        super(NbiServiceUnavailableException, self).__init__(status_code, response_text, json, *args, **kwargs)

    def __str__(self):
        return 'Service is unavailable.'


class NbiBadRequestException(NbiRequestException):
    def __init__(self, status_code, response_text='', json=None, *args, **kwargs):
        super(NbiBadRequestException, self).__init__(status_code, response_text, json, *args, **kwargs)

    def __str__(self):
        return 'Bad Request.'


class NbiConnectionException(Exception):

    def __init__(self, *args, **kwargs):
        super(NbiConnectionException, self).__init__(*args, **kwargs)
        self.status_code = kwargs['status_code'] if 'status_code' in kwargs else 999
        self.json = None
        self.response_text = ''

    def __str__(self):
        return 'Failed to connect to Service.'


class NbiUnknownServiceHostException(NbiConnectionException):
    def __init__(self, *args, **kwargs):
        super(NbiUnknownServiceHostException, self).__init__(*args, **kwargs)

    def __str__(self):
        return 'Failed to determine ENM\'s host name.'


class LoginResponseParser(HTMLParser, object):
    """
    Class that can determine from a http response if it is a response from ENM
    that redirects the browser to the ENM password change page.

    Parsing of the content is required because there is nothing in the headers
    that could help to identify this scenario.

    Usage:
        LoginResponseParser(r.text).password_change_redirect()
    """
    _BODY_TAG = 'body'
    _ONLOAD_ATT = 'onload'
    _PASSWORD_CHANGE_VALUE = 'redirectToEnmPasswordChange'

    def __init__(self, text):
        super(LoginResponseParser, self).__init__()
        self._password_change_redirect = False
        self.feed(text)

    def password_change_redirect(self):
        return self._password_change_redirect

    def handle_starttag(self, tag, attributes):
        # Looking for the onload attribute in the body tag eg: <body id="null" onload="redirectToEnmPasswordChange()"/>
        if tag == self._BODY_TAG:
            for attribute in attributes:
                # Attribute is represented with a tuple: ('onload', 'redirectToEnmPasswordChange()')
                if len(attribute) == 2 and self._ONLOAD_ATT == attribute[0]:
                    if self._PASSWORD_CHANGE_VALUE in attribute[1]:
                        self._password_change_redirect = True
                        return
            self._password_change_redirect = False

    def reset(self):
        self._password_change_redirect = False
        return super(LoginResponseParser, self).reset()
