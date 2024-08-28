from .terminal.terminal import EnmTerminal
from .command.command import EnmCommand


class EnmSession(object):
    """
    This class holds a session to a running ENM deployment
    """
    def __init__(self, session=None):
        self._session = session

    def terminal(self):
        """
        Returns an instance of EnmTerminal
        """
        return EnmTerminal(self._session)

    def command(self):
        """
        Returns an instance of EnmCommand
        """
        return EnmCommand(self._session)


class UnauthenticatedEnmSession(object):
    """
    This class holds a unauthenticated session to a running ENM deployment
    """

    def __init__(self, session=None):
        self._session = session

    def with_credentials(self, authenticator):
        self._session.open_session(authenticator)

        return EnmSession(self._session)
