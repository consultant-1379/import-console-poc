import io
import os
import logging
from mock import MagicMock, patch
from nose import with_setup
from nose.tools import assert_raises
from responses import activate as mock_responses
from enmscripting.exceptions import ConfigurationError
from enmscripting.private.session import ExternalSession, InternalSession, _ENV_CLIENT_SCRIPTING_VERIFY
from .test_open_internal_session import setup_func, teardown_func


logging.basicConfig()
logging.getLogger().setLevel(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_cert_verification_default_false():
    with patch.dict('os.environ', {_ENV_CLIENT_SCRIPTING_VERIFY: 'False'}):
        session = ExternalSession()
        assert session._verify is False


def test_cert_verification_can_be_set_to_true():
    with patch.dict('os.environ', {_ENV_CLIENT_SCRIPTING_VERIFY: 'True'}):
        session = ExternalSession()
        assert session._verify is True


def test_cert_verification_can_be_set_to_valid_path():
    cert_file_name = 'ca_cert.crt'
    full_path = os.path.abspath(cert_file_name)
    with io.open(full_path, 'wb+') as cert_file:
        cert_file.write(b'CERT_CONTENT')

    with patch.dict('os.environ', {_ENV_CLIENT_SCRIPTING_VERIFY: full_path}):
        session = ExternalSession()
        assert full_path == session._verify

    if os.path.isfile(cert_file.name):
        os.remove(cert_file.name)


def test_cert_verification_raises_error_with_invalid_path():
    session = ExternalSession()
    with patch.dict('os.environ', {_ENV_CLIENT_SCRIPTING_VERIFY: '/fake/path/file.crt'}):
        assert_raises(ConfigurationError, session._server_verify)


@mock_responses
@with_setup(setup_func, teardown_func)
def test_cert_verification_default_false_internal_session():
    with patch.dict('os.environ', {_ENV_CLIENT_SCRIPTING_VERIFY: 'True'}):
        session = InternalSession()
        assert session._verify is False


def test_execute_post_verify_default_false():
    with patch('enmscripting.private.session.Session.post') as session_post:
        session = ExternalSession()
        session.post('http://the_url')

        _, kwargs = session_post.call_args

        assert not kwargs.get('verify')


def test_execute_post_verify_true():
    with patch('enmscripting.private.session.Session.post') as session_post:
        with patch.dict('os.environ', {_ENV_CLIENT_SCRIPTING_VERIFY: 'True'}):
            session = ExternalSession()
            session.post('http://the_url')

            _, kwargs = session_post.call_args

            assert kwargs.get('verify')


def test_execute_get_verify_default_false():
    with patch('enmscripting.private.session.Session.get') as session_get:
        session = ExternalSession()
        session.get('http://the_url')

        _, kwargs = session_get.call_args

        assert not kwargs.get('verify')


def test_execute_get_verify_true():
    with patch('enmscripting.private.session.Session.get') as session_get:
        with patch.dict('os.environ', {_ENV_CLIENT_SCRIPTING_VERIFY: 'True'}):
            session = ExternalSession()
            session.get('http://the_url')

            _, kwargs = session_get.call_args

            assert kwargs.get('verify')


def test_execute_head_verify_default_false():
    with patch('enmscripting.private.session.Session.head') as session_head:
        session = ExternalSession()
        session.head('http://the_url')

        _, kwargs = session_head.call_args

        assert not kwargs.get('verify')


def test_execute_head_verify_true():
    with patch('enmscripting.private.session.Session.head') as session_head:
        with patch.dict('os.environ', {_ENV_CLIENT_SCRIPTING_VERIFY: 'True'}):
            session = ExternalSession()
            session.head('http://the_url')

            _, kwargs = session_head.call_args

            assert kwargs.get('verify')


def test_execute_verify_overwrite():
    with patch('enmscripting.private.session.Session.get') as session_get:
        with patch.dict('os.environ', {_ENV_CLIENT_SCRIPTING_VERIFY: 'True'}):
            session = ExternalSession()

            session.get('http://the_url')
            _, kwargs = session_get.call_args
            assert kwargs['verify']

            session.get('http://the_url', verify=False)
            _, kwargs = session_get.call_args
            assert not kwargs['verify']
