from mock import MagicMock
from nose.tools import assert_raises
from enmscripting.command.command import *
from .json_generator import *
import logging

logging.basicConfig()
logging.getLogger().setLevel(level=logging.DEBUG)


def test_create_command_output_with_command():
    json = generate_json(0, 0, 0, 0, 0)
    result = CommandOutput(200, True, json)
    assert result._command == COMMAND


def test_command_output_error_status():
    json = generate_json(0, 0, 0, 0, 0)
    result = CommandOutput(200, False, json)
    assert_raises(IllegalStateException, result.get_output)


def test_command_output_factory_create_output():
    json_output = generate_json(1, 0, 0, 0)
    handler = MagicMock()
    terminal_output_factory = CommandOutputFactory()
    expected_output = CommandOutput(200, True, json_output, handler)
    actual_output = terminal_output_factory.create_output(200, True, json_output, handler)
    assert expected_output.__getattribute__('_output') == actual_output.__getattribute__('_output')
    assert expected_output.__getattribute__('_handler') == actual_output.__getattribute__('_handler')
    assert expected_output.__getattribute__('_http_response_code') == actual_output.__getattribute__(
        '_http_response_code')
    assert expected_output.__getattribute__('_parsed_json') == actual_output.__getattribute__('_parsed_json')
