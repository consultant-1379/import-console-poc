from enmscripting.enmsession import EnmSession
from enmscripting.terminal.terminal import EnmTerminal
from enmscripting.command.command import EnmCommand


def test_terminal():
    enm_session = EnmSession()
    assert enm_session.terminal()
    assert isinstance(enm_session.terminal(), EnmTerminal)


def test_command():
    enm_session = EnmSession()
    assert enm_session.command()
    assert isinstance(enm_session.command(), EnmCommand)
