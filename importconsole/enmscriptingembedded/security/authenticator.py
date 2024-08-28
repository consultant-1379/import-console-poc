from __future__ import absolute_import
import logging
import hashlib
import io
from ..private.overrides import overrides
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

logger = logging.getLogger(__name__)

_AUTH_COOKIE_KEY = 'iPlanetDirectoryPro'


class Authenticator(object):
    """
    Base Authenticator class that defines the Authenticator contract.
    """
    def __init__(self):
        pass

    def authenticate(self, session):
        """
        Performs the authentication on the given session.
        :param session: ExternalSession or InternalSession to be authenticated
        :return: void
        """
        pass

    def logout(self, session):
        """
        Clear the authentication credentials from the session.
        :param session: ExternalSession or InternalSession
        :return: void
        """
        pass


class UsernameAndPassword(Authenticator):
    """
    Authenticator that uses username and password to perform the authentication on
    a session.
    """
    _AUTH_ERROR_CODE = 'x-autherrorcode'
    _AUTH_OK = '0'

    def __init__(self, username, password):
        super(UsernameAndPassword, self).__init__()
        self._username = username
        self._password = password

    @overrides
    def authenticate(self, session):
        logger.debug('Authenticating user [%s]', self._username)

        auth_response = session.post(''.join((session.url(), '/login')),
                                     data={'IDToken1': self._username, 'IDToken2': self._password},
                                     allow_redirects=False)

        logger.debug('Login server response is [%s][%s]', str(auth_response.status_code), auth_response.text)

        if self._AUTH_ERROR_CODE not in auth_response.headers:
            if LoginResponseParser(auth_response.text).password_change_redirect():
                # Redirect detected
                logger.error('Invalid login, password change required for user [%s]. '
                             'Please change it via ENM login page', self._username)
                raise ValueError('Invalid login, password change required for user [%s]. '
                                 'Please change it via ENM login page' % self._username)
            else:
                # Not ENM server
                logger.error('Failed to open session. Please make sure the URL [%s] is a valid ENM URL', session.url())
                raise ValueError(
                    'Failed to open session. Please make sure the URL [%s] is a valid ENM URL' % session.url())
        elif auth_response.headers[self._AUTH_ERROR_CODE] is not self._AUTH_OK \
                or _AUTH_COOKIE_KEY not in session.cookies.keys():
            # Authentication failed
            logger.error('Invalid login, credentials are invalid for user [%s]', self._username)
            raise ValueError('Invalid login, credentials are invalid for user [%s]' % self._username)

        logger.debug('Session opened towards [%s] and user [%s] is authenticated', session.url(), self._username)
        self._password = None

    @overrides
    def logout(self, session):
        session.get(''.join((session.url(), '/logout')), allow_redirects=True)


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

    def reset(self):
        self._password_change_redirect = False
        return super(LoginResponseParser, self).reset()


class SsoToken(Authenticator):
    """
    The SsoToken authenticator sets the provided SSO token on the session.
    """
    def __init__(self, sso_token):
        super(SsoToken, self).__init__()
        self._ssoToken = sso_token

    @overrides
    def authenticate(self, session):
        if self._ssoToken is None:
            return
        current_token = session.cookies.get(_AUTH_COOKIE_KEY)
        if current_token != self._ssoToken:
            session.cookies[_AUTH_COOKIE_KEY] = self._ssoToken
            logger.debug('New authentication cookie is set [%s]', self._auth_cookie_hash())
        else:
            logger.debug('Authentication cookie already set [%s]', self._auth_cookie_hash())

    @overrides
    def logout(self, session):
        self._ssoToken = ''

    def token(self):
        return self._ssoToken

    @classmethod
    def from_file(self, token_file_path):
        return _SsoTokenFromFile(token_file_path)

    @classmethod
    def _get_hash(cls, str_to_hash='', encoding='utf-8'):
        m = hashlib.md5()
        m.update(str_to_hash.encode(encoding))
        return m.hexdigest()

    def _auth_cookie_hash(self):
        return self._get_hash(self._ssoToken)


class _SsoTokenFromFile(SsoToken):
    """
    This class is a extension of SsoToken which read the token from a file on file-system.
    The 'authenticate' method can be called multiple times, and on each call the file will be read again
    and if the token has changed, the new token will be set on the session.
    """
    def __init__(self, token_file):
        super(_SsoTokenFromFile, self).__init__(None)
        self._token_file = token_file

    @overrides
    def authenticate(self, session):
        try:
            self._load_cookie()
        finally:
            super(_SsoTokenFromFile, self).authenticate(session)

    def _load_cookie(self):
        logger.debug('Loading cookie from file [%s]', self._token_file)
        try:
            with io.open(self._token_file, 'r') as cookie:
                self._ssoToken = cookie.readline().strip()
        except (OSError, IOError) as e:
            logger.exception(e)
            self._ssoToken = ''
            raise ValueError('Invalid token file [%s]' % self._token_file)
