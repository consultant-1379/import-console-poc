from nose.tools import assert_raises
from enmscripting import *
from enmscripting.common.output import Output
from .json_generator import *


def test_output():
    out = Output(200, True, None)
    assert out.http_response_code() == 200
    assert out.is_command_result_available() is True


def test_output_good_json():
    json = generate_json(0, 0, 0, 0, 0)
    output = Output(200, True, json)
    assert output._parsed_json is not None, 'expecting Output to have _parsed_json. There is none.'


def test_create_command_output_bad_json():
    bad_json = r"'elements' : []"
    assert_raises(InternalError, Output, 200, True, bad_json)
