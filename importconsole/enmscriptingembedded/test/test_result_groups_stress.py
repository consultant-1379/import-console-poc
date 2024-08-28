from __future__ import print_function
import logging
import datetime
# import time
# from memory_profiler import profile
from nose.tools import nottest
from enmscripting.command.command import CommandOutput
from .json_generator import *
from .element_iterator import *

logging.basicConfig()
logging.getLogger().setLevel(level=logging.DEBUG)


# STRESS

def test_big_output_10k_0k():
    assert_big_output(10000, 0, 0, 0)


@nottest
def test_big_output_20k_0k():
    assert_big_output(20000, 0, 0, 0)


@nottest
def test_big_output_50k_0k():
    assert_big_output(50000, 0, 0, 0)


def test_big_output_1k_1k_10k():
    assert_big_output(1000, 10, 100, 10)


@nottest
def test_big_output_5k_5k_50k():
    assert_big_output(5000, 100, 50, 10)


@nottest
def test_memory():
    assert_big_output(2, 25, 50, 10)


# HELPER METHODS
# @profile
def assert_big_output(lines, tables, rows, columns):
    # print(lines, tables, rows, columns)

    t1 = datetime.datetime.now()
    big_json = generate_json(lines, tables, rows, columns)
    t2 = datetime.datetime.now()
    # print('Test file generated: ' + str(t2-t1))

    result = CommandOutput(200, True, big_json)
    t3 = datetime.datetime.now()
    # print('CommandOutput object created: ', str(t3-t2))

    output = result.get_output()
    t4 = datetime.datetime.now()
    # print('get_output: ', str(t4-t3))

    result_string = to_string_iterate(output)
    t5 = datetime.datetime.now()
    # print('Result iterated trough: ', str(t5-t4))

    act_cells = result_string.count('cell')
    exp_cells = tables*rows*columns

    assert exp_cells == act_cells, 'There should be ' + str(exp_cells) + ' cells, but there was[' + str(act_cells) + ']'
    assert lines == result_string.count('line_number_'), 'There should be ' + str(lines) + ' lines'

if __name__ == '__main__':
    test_memory()
