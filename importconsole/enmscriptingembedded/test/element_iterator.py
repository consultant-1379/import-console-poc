from enmscripting import *


def to_string_iterate(root_element):
    """
    Iterates through the result and generates a string representation of the output
    similar to CLI output
    """
    result_string = ''
    for elem in root_element:
        if type(elem) is TextElement:
            result_string += str(elem.value()) + '\n'
        elif type(elem) is FileElement:
            result_string += str(elem.get_name()) + '\n'
        elif _is_table(elem):
            # Header row
            for cell in elem[0]:
                result_string += cell.labels()[0] + '\t'
            result_string += '\n'
            # Table rows
            for row in elem:
                for cell in row:
                    result_string += str(cell.value()) + '\t'
                result_string += '\n'
        else:
            result_string += str(elem) + '\n'

    return result_string


def to_string_recursive(root_element, level=0):
    """
    Iterates through the result (recursively) and generates a string representation of the output in a
    tree like format
    """
    result = ''
    if level is not 0:  # Top level is a group no need to print
        result += '\t' * (level - 1)
        result += str(root_element) + '\n'
    if type(root_element) is ElementGroup:
        for e in root_element:
            # Recursive call
            result += to_string_recursive(e, level + 1)
    return result


def to_string_recursive_types(element, level=0, index={}):
    """
    Iterates through the result (recursively) and generates a string representation of the output that
    shows the structure of the result:

    <ElementGroup>
        <TextElement> element[0]  # line_number_0
        <TextElement> element[1]  # line_number_1
        <TextElement> element[2]  # line_number_2
        <ElementGroup>table_3 =  element[3]  # table0
                <ElementGroup>row_30 =  element[3][0]
                        <TextElement>cell_300 =  element[3][0][0]  # cell_value_at_000
                        <TextElement>cell_301 =  element[3][0][1]  # cell_value_at_001
                        <TextElement>cell_302 =  element[3][0][2]  # cell_value_at_002
                <ElementGroup>row_31 =  element[3][1]
                        <TextElement>cell_310 =  element[3][1][0]  # cell_value_at_010
                        <TextElement>cell_311 =  element[3][1][1]  # cell_value_at_011
                        <TextElement>cell_312 =  element[3][1][2]  # cell_value_at_012
        <ElementGroup>table_4 =  element[4]  # table1
                <ElementGroup>row_40 =  element[4][0]
                        <TextElement>cell_400 =  element[4][0][0]  # cell_value_at_100
                        <TextElement>cell_401 =  element[4][0][1]  # cell_value_at_101
                        <TextElement>cell_402 =  element[4][0][2]  # cell_value_at_102
                <ElementGroup>row_41 =  element[4][1]
                        <TextElement>cell_410 =  element[4][1][0]  # cell_value_at_110
                        <TextElement>cell_411 =  element[4][1][1]  # cell_value_at_111
                        <TextElement>cell_412 =  element[4][1][2]  # cell_value_at_112
        <FileElement>file_5 =  element[5]  # file_0
        <FileElement>file_6 =  element[6]  # file_1
    """

    # Keep track of where the iteration is in the structure
    if level not in index.keys():
        # Going down 1 level from previous iteration
        index[level] = 0
    else:
        # Update level index
        index[level] += 1
        if len(index) > level + 1:
            # Coming back 1 level from previous iteration / reset the numbers
            for i in range(level + 1, len(index)):
                del index[i]

    # Tab the result according to its depth in the tree
    result = '\n'
    result += '\t' * level

    # Get the element description, eg: <TextElement> element[2]  # line_number_2
    result += _get_element_desc(element, level, index)

    # Recursive call
    if type(element) is ElementGroup:
        for e in element:
            # Recursive call
            result += to_string_recursive_types(e, level + 1, index)

    return result


def _get_element_desc(element, level=0, index={}):
    """
    Generates element string, eg:
    # (1)           (2)  (3)(4)            (5)
    # <ElementGroup>table_3 =  element[3]  # table0
    # <TextElement>cell_300 =  element[3][0][0]  # cell_value_at_000
    """

    # (1)
    # <TextElement>
    result = '<' + str(type(element).__name__) + '> '

    # Index of the element, eg: 300
    index_string = ''.join(str(x) for x in index.values())[1:]

    # (2)
    result += _get_label(element)

    if level is not 0:
        # (4)
        # <type>_300 =
        if _get_label(element) is not '':
            result += '_' + index_string + ' = '

        # (4)
        # element[2][3][4]
        result += 'element'
        for c in index_string:
            result += '[' + c + ']'

        # (5)
        #  # cell_value_at_000
        if type(element) is ElementGroup:
            if len(element.labels()) > 0:
                result += '  # ' + element.labels()[0]
        elif type(element) is TextElement:
            result += '  # ' + element.value()
        elif type(element) is FileElement:
            result += '  # ' + element.get_name()

    return result


def _get_label(element):
    if _is_cell(element):
        return 'cell'
    elif _is_row(element):
        return 'row'
    elif _is_table(element):
        return 'table'
    elif type(element) is FileElement:
        return 'file'
    else:
        return ''


def _is_row(element):
    if type(element) is ElementGroup:
        return len(element.groups()) == 0
    return False


def _is_table(element):
    if type(element) is ElementGroup:
        return len(element.groups()) == len(element)
    return False


def _is_cell(element):
    if type(element) is TextElement:
        return len(element.labels()) != 0
