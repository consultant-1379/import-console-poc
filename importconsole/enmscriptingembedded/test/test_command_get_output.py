import logging
from enmscripting.command.command import CommandOutput
from .element_iterator import *
from .json_generator import *

logging.basicConfig()
logging.getLogger().setLevel(level=logging.DEBUG)

""" Most of the tests are working based on this example output (see json_generator)
# first_line
# column0 column1 column2
  cell00  cell01  cell02
  cell10  cell11  cell12
  cell20  cell21  cell22
# last_line
"""


def test_get_output_lines():
    output = CommandOutput(200, True, response_json).get_output()

    assert 3 is len(output), 'Output size should be 3, but got ' + str(len(output))
    assert first_line == output[0].value()
    assert last_line == output[2].value()


def test_get_output_only_lines():
    json = generate_json(2, 0, 0, 0, 0)
    result = CommandOutput(200, True, json)

    output = result.get_output()

    assert len(output) == 2, "expecting 2 element, found %s" % str(len(output))
    assert output[0].value() == "line_number_0", "expecting [line_number_0], found %s" % output[0].value()


def test_get_output_new_type():
    result = CommandOutput(200, True, simple_response_json)
    new_type = result.get_output()[2]

    assert type(new_type) is Element

    attributes = new_type.attributes()
    assert len(attributes) is 3
    assert attributes['type'] == 'new_type'
    assert attributes['pub1'] == 'pub1'


# TYPES

def test_get_output_types():
    output = CommandOutput(200, True, response_json).get_output()

    assert 3 is len(output), 'Output size should be 3'
    assert type(output[0]) is TextElement, 'First element should be TextElement'
    assert type(output[1]) is ElementGroup, 'Second element should be ElementGroup'
    assert type(output[2]) is TextElement, 'Third element should be TextElement'

    assert isinstance(output[0], TextElement), 'First element should be TextElement'
    assert isinstance(output[1], ElementGroup), 'Second element should be ElementGroup'
    assert isinstance(output[2], TextElement), 'Third element should be TextElement'


# ITERATE

def test_table_iterate(table=None):
    result = CommandOutput(200, True, response_json)
    if table is None:
        table = result.get_output()[1]
    for row in table:
        for cell in row:
            assert_substring_in_list(cell.labels(), 'column')  # columnX
            assert 'cell' in cell.value()  # cellXX


def test_result_iterate_string():
    output = CommandOutput(200, True, response_json).get_output()
    result_string = to_string_iterate(output)

    # print result_string

    assert 9 is result_string.count('cell'), 'There should be 9 cells'
    assert 2 is result_string.count('_line'), 'There should be 2 lines'
    assert 3 is result_string.count('column'), 'There should be 3 columns'


def test_result_string():
    output = CommandOutput(200, True, response_json).get_output()

    result_string = str(output)
    # print '\n', result_string
    assert result_string == '(first_line, ' \
                            '((cell00, cell01, cell02), ' \
                            '(cell10, cell11, cell12), ' \
                            '(cell20, cell21, cell22)), ' \
                            'last_line)'


def test_result_structure():
    output = CommandOutput(200, True, response_json).get_output()
    result_string = to_string_recursive_types(output)

    # print result_string

    assert 9 is result_string.count('cell_'), 'There should be 9 cells'
    assert 3 is result_string.count('row_'), 'There should be 3 rows'
    assert 1 is result_string.count('table_'), 'There should be 1 table'

    # 1 top level + 1 table  + 3 rows
    assert 1+1+3 is result_string.count('ElementGroup'), 'There should be 5 ElementGroup'
    # 2 line + 9 cells
    assert 2+9 is result_string.count('TextElement'), 'There should be 11 TextElement'

# INDEXING


def test_indexing_output():
    output = CommandOutput(200, True, response_json).get_output()

    assert first_line == output[0].value()
    assert first_line == output[-3].value()

    assert last_line == output[2].value()
    assert last_line == output[-1].value()


def test_indexing_multiple():
    result = CommandOutput(200, True, response_json)
    cell00 = result.get_output()[1][0][0]
    assert 'cell00' == cell00.value()

    cell22 = result.get_output()[1][-1][-1]
    assert 'cell22' == cell22.value()


def test_indexing_type_error():
    result = CommandOutput(200, True, response_json)
    # Going too deep
    try:
        cell_000 = result.get_output()[1][0][0][0]
        assert False, 'Should throw TypeError'
    except TypeError:
        pass


def test_indexing_index_error():
    result = CommandOutput(200, True, response_json)
    # Index out of bounds
    try:
        cell_04 = result.get_output()[1][0][4]
        assert False, 'Should throw IndexError'
    except IndexError:
        pass


# LABELS / FIND BY LABEL

def test_labels():
    output = CommandOutput(200, True, response_json).get_output()

    # Top level elements
    assert 0 is len(output[0].labels()), 'First element should have no labels'
    assert 1 is len(output[1].labels()), 'Second element should have 1 label'
    assert 0 is len(output[2].labels()), 'Third element should have no labels'

    # Table
    table = output[1]
    assert 'table' == table.labels()[0]

    # Table rows
    for i in range(len(table)):
        assert 0 is len(output[1][i].labels()), 'Row should not have labels'

    # Table cells
    for i in range(len(table)):
        row = table[i]
        for j in range(len(row)):
            cell = row[j]
            assert 1 is len(cell.labels()), 'Cell should not 1 label'
            assert_substring_in_list(cell.labels(), 'column')


def test_find_by_label_table():
    result = CommandOutput(200, True, response_json)
    table = result.get_output().find_by_label('table')[0]

    test_table_iterate(table)


def test_find_by_label_cell():
    result = CommandOutput(200, True, response_json)
    table = result.get_output()[1]
    row_nr = 0
    col_nr = 1

    label_column = 'column' + str(col_nr)  # column1
    cells = table[row_nr].find_by_label(label_column)
    assert 1 is len(cells), 'One column should have the label column1'

    exp_cell_value = 'cell' + str(row_nr) + str(col_nr)  # cell01
    act_cell_value = cells[0].value()
    assert exp_cell_value == act_cell_value


# FIND BY TYPE

def test_find_by_type():
    output = CommandOutput(200, True, response_json).get_output()
    table = output._find_by_type(ElementGroup)
    assert len(table) is 1

    lines = output._find_by_type(TextElement)
    assert len(lines) is 2

    non_existent = output._find_by_type(object)
    assert len(non_existent) is 0


def test_find_by_type_value():
    output = CommandOutput(200, True, response_json).get_output()
    table = output._find_by_type_value(ElementGroup.TYPE)

    assert len(table) is 1

    lines = output._find_by_type_value(TextElement.TYPE)
    assert len(lines) is 2

    non_existent = output._find_by_type_value('fake')
    assert len(non_existent) is 0


def test_find_by_label_empty():
    result = CommandOutput(200, True, response_json)

    # Find top level elem with label
    found = result.get_output().find_by_label('fake')
    assert 0 is len(found)

    # Find row with label
    found = result.get_output()[1].find_by_label('fake')
    assert 0 is len(found)

    # Find cell with label
    found = result.get_output()[1][1].find_by_label('fake')
    assert 0 is len(found)


# GROUPS / HAS GROUPS / HAS ELEMENTS

def test_result_groups():
    output = CommandOutput(200, True, response_json).get_output()
    table = output.groups()[0]

    test_table_iterate(table)


def test_result_has_groups_true():
    output = CommandOutput(200, True, response_json).get_output()
    assert output.has_groups()


def test_result_has_groups_false():
    json = generate_json(2, 0, 0, 0, 2)
    output = CommandOutput(200, True, json).get_output()
    assert not output.has_groups()


def test_result_has_elements_true():
    o1 = CommandOutput(200, True, response_json).get_output()
    assert o1.has_elements()

    json_nogroup = generate_json(2, 0, 0, 0, 2)
    o2 = CommandOutput(200, True, json_nogroup).get_output()
    assert o2.has_elements()


def test_result_has_elements_false():
    group = ElementGroup()
    assert not group.has_elements()


def test_get_multiple_groups():
    json = generate_json(1, 2, 1, 2, 0)
    output = CommandOutput(200, True, json).get_output()
    assert output.has_groups()
    assert len(output.groups()) == 2


def test_partial_groups_are_merged():
    json = generate_json(1, 2, 1, 2, 0, terminated=False)
    command_output = CommandOutput(200, True, json)
    command_output._append_response(generate_json(1, 2, 2, 2, 0, terminated=False))
    command_output._append_response(generate_json(1, 1, 3, 2, 0, terminated=True))
    output = command_output.get_output()
    assert output.has_groups()
    assert len(output.groups()) == 2
    assert len(output.groups()[0]) == 6
    assert len(output.groups()[1]) == 3


# HELPER METHODS

def assert_substring_in_list(list, substring):
    found = False
    for item in list:
        if substring in item:
            found = True
            break
    assert found, 'Substring [' + substring + '] is not founbd in list: ' + str(list)
