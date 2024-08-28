import logging
from mock import MagicMock
from nose.tools import assert_raises
from enmscripting.terminal.terminal import (TerminalOutput, EnmTerminal, TerminalOutputFactory)
from enmscripting import *
from .json_generator import *

logging.basicConfig()
logging.getLogger().setLevel(level=logging.DEBUG)


def test_enm_terminal_execute():
    json_output = generate_json(1, 0, 0, 0)
    enm_terminal = EnmTerminal()
    handler = MagicMock()
    terminal_output = TerminalOutput(200, True, json_output)
    handler.execute.return_value = terminal_output
    enm_terminal._handler = handler

    terminal_output = enm_terminal.execute('abc')
    lines = terminal_output.get_output()
    assert len(lines) == 1, 'Output size should be 1'
    lines = terminal_output.get_output()
    assert len(lines) == 1, 'Output size should be 1 second time too'


def test_terminal_output_lines():
    json_output = generate_json(1, 0, 0, 0)
    output = TerminalOutput(200, True, json_output)
    lines = output.get_output()
    assert len(lines) == 1, 'Output size should be 1'


def test_terminal_output_empty_not_ignored():
    json_output = empty_line_response_json
    output = TerminalOutput(200, True, json_output)
    lines = output.get_output()
    assert len(lines) == 3, 'Wrong output size of : ' + str(len(lines))


def test_terminal_output_table():
    json_output = generate_json(0, 1, 1, 4)
    output = TerminalOutput(200, True, json_output)
    lines = output.get_output()
    # Title + Header row + 1 Value row = 3
    assert len(lines) == 3, 'Output size should be 3, found : ' + str(len(lines))
    # Assert header row comes first
    assert lines[1].startswith('column0') is True
    # Assert each row contains TABs
    for line in lines[1:]:
        assert ('\t' in line) is True, 'Line should contain TABs'


def test_terminal_output_lines_and_tables():
    json_output = generate_json(2, 2, 2, 4)
    output = TerminalOutput(200, True, json_output)
    lines = output.get_output()
    # Length is: 1 + 1 + 4 + 4
    assert len(lines) == 10, 'Output size should be 10'


def test_terminal_output_partial_tables_are_merged():
    json_output_part1 = generate_json(2, 1, 2, 4, terminated=False)
    json_output_part2 = generate_json(2, 1, 3, 4)
    output = TerminalOutput(200, True, json_output_part1)
    output._append_response(json_output_part2)

    lines = output.get_output()

    # Title + Header row + 5 Value row  + 4 lines = 11
    assert len(lines) == 11, 'Output size should be 11, found : ' + str(len(lines))

    # Assert lines comes first
    assert lines[0].startswith('line_number') is True
    assert lines[1].startswith('line_number') is True
    # Assert header
    assert lines[3].startswith('column0') is True
    # Assert each row contains TABs
    for line in lines[4:8]:
        assert ('\t' in line) is True, 'Line should contain TABs'
    # Assert ends with last 2 lines
    assert lines[-1].startswith('line_number') is True
    assert lines[-2].startswith('line_number') is True


def test_not_success_raises_exception():
    output = TerminalOutput(200, False, None)
    assert_raises(IllegalStateException,  output.get_output)


def test_response_incorrect_format():
    result_string_incorrect = '{"NOToutput": "success lines"}'
    output = TerminalOutput(200, True, result_string_incorrect)
    assert_raises(InternalError,  output.get_output)


def test_response_not_proper_json():
    result_string_not_proper_json = \
        '{"output" : "commmand as ok", ' \
        '"v" : "1"' \
        ''  # '}' missing from the end
    assert_raises(InternalError, TerminalOutput, 200, True, result_string_not_proper_json)


def test_execute_download_has_files_pos():
    """
    Test the scenario when the response contains a 'download' response
    """
    cmd_output = TerminalOutput(200, True, generate_json(0, 0, 0, 0, 1))
    assert cmd_output.has_files() is True


def test_execute_download_get_files():
    terminal = MagicMock()
    cmd_output = TerminalOutput(200, True, generate_json(0, 0, 0, 0, 1), terminal)
    files = cmd_output.files()

    assert files, "expected a list of files"
    assert len(files) == 1, "expected 1 file, found :" + str(len(files))


def test_execute_download_get_files_with_no_files():
    cmd_output = TerminalOutput(200, True, generate_json(1, 0, 0, 0))
    files = cmd_output.files()

    assert files is not None, "expected a list of files"
    assert len(files) == 0, "expected 0 files, found :" + str(len(files))


def test_execute_download_has_files_neg():
    """
    Test the scenario when the response contains no 'download' response
    """
    cmd_output = TerminalOutput(200, True, generate_json(1, 0, 0, 0))
    assert cmd_output.has_files() is False


def test_terminal_output_factory_create_output():
    json_output = generate_json(1, 0, 0, 0)
    handler = MagicMock()
    terminal_output_factory = TerminalOutputFactory()
    expected_output = TerminalOutput(200, True, json_output, handler)
    actual_output = terminal_output_factory.create_output(200, True, json_output, handler)
    assert expected_output.__getattribute__('_result_lines') == actual_output.__getattribute__('_result_lines')
    assert expected_output.__getattribute__('_http_response_code') == actual_output.__getattribute__(
        '_http_response_code')
    assert expected_output.__getattribute__('_success') == actual_output.__getattribute__('_success')
    assert expected_output.__getattribute__('_parsed_json') == actual_output.__getattribute__('_parsed_json')

empty_line_response_json = '{"output": ' \
                           '   {"type": "group", "_elements": ' \
                           '       [{"type": "text", "value": ""},' \
                           '        {"type": "text", "value": "non empty line"},' \
                           '        {"type": "text", "value": ""}]' \
                           '	},' \
                           ' "command": "the command",' \
                           ' "_response_status": "COMPLETE",' \
                           ' "v": "2"' \
                           '}'
