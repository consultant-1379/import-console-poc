COMMAND = 'cmedit get * MeContext.* -t'


def generate_json(nr_lines, nr_tables, nr_rows, nr_columns, nr_of_files=0, terminated=True):
    """
    Generates a JSON with a number of lines tables as specified in the parameters.
    """
    response_prefix = '{"output": ' \
                      '   {"type": "group", "_elements": ['
    lines = ''
    for l in range(nr_lines):
        # Element
        lines += '{"type": "text", "value": "line_number_' + str(l) + '"},'

    tables = ''
    for t in range(nr_tables):
        # Table group
        tables += '{"type": "group", "_group_key": "' + str(t) + '", "_label" : ["table' + str(t) + '"], "_elements": ['
        for r in range(nr_rows):
            # Row group
            tables += '{"type": "group","_elements": ['
            for c in range(nr_columns):
                # Cell elements
                tables += '{"type": "text","_label": ["column' + str(c) + \
                          '"],"value": "cell_value_at_' + str(t) + str(r) + str(c) + '"},'
            tables = tables[:-1]
            tables += ']},'
        tables = tables[:-1]
        tables += ']},'

    files = ''
    for f in range(nr_of_files):
        # File
        files += '{"type": "attachment",' \
                 ' "_fileId": "file_' + str(f) + '", ' \
                 ' "_applicationId": "app_id_' + str(f) + '", ' \
                 ' "name": "file_' + str(f) + '"},'

    data = lines + tables + files
    data = data[:-1]

    response_status = "COMPLETE" if terminated else "FETCHING"
    response_postfix = ']},' \
                       ' "command": "' + COMMAND + '",' \
                       ' "_response_status": "' + response_status + '",' \
                       ' "v": "2"' \
                       '}'

    json = response_prefix + data + response_postfix

    return json


# DATA

first_line = 'first_line'
last_line = 'last_line'

response_json = '{"output": ' \
                '   {"type": "group", "_elements": ' \
                '       [{"type": "text", "value": "' + first_line + '"},' \
                '        {"type": "group", "_group_key": "groupid", "_label" : ["table"], "_elements": ' \
                '           [{"type": "group","_elements": ' \
                '               [{"type": "text","_label": ["column0"],"value": "cell00"},' \
                '                {"type": "text","_label": ["column1"],"value": "cell01"},' \
                '                {"type": "text","_label": ["column2"],"value": "cell02"}]' \
                '            },' \
                '            {"type": "group","_elements": ' \
                '               [{"type": "text","_label": ["column0"],"value": "cell10"},' \
                '                {"type": "text","_label": ["column1"],"value": "cell11"},' \
                '                {"type": "text","_label": ["column2"],"value": "cell12"}]' \
                '            },' \
                '            {"type": "group","_elements": ' \
                '               [{"type": "text","_label": ["column0"],"value": "cell20"},' \
                '                {"type": "text","_label": ["column1"],"value": "cell21"},' \
                '                {"type": "text","_label": ["column2"],"value": "cell22"}]' \
                '            }]' \
                '        },' \
                '        {"type": "text", "value": "' + last_line + '"}]' \
                '	},' \
                ' "command": "' + COMMAND + '",' \
                ' "_response_status": "COMPLETE",' \
                ' "v": "2"' \
                '}'

simple_response_json = '{"output": ' \
                       '   {"type": "group", "_elements": ' \
                       '       [{"type": "text", "value": "' + first_line + '"},' \
                       '        {"type": "group", "_group_key": "groupid", "_label" : ["table"], "_elements": ' \
                       '           [{"type": "group","_elements": ' \
                       '               [{"type": "text","_label": ["column0"],"value": "cell00"},' \
                       '                {"type": "text","_label": ["column1"],"value": "cell01"}]' \
                       '            },' \
                       '            {"type": "group","_elements": ' \
                       '               [{"type": "text","_label": ["column0"],"value": "cell10"},' \
                       '                {"type": "text","_label": ["column1"],"value": "cell11"}]' \
                       '            }]' \
                       '        },' \
                       '        {"type": "new_type", "_private": "private", "pub1": "pub1", "pub2": "pub2"},' \
                       '        {"type": "text", "value": "' + last_line + '"}]' \
                       '	},' \
                       ' "command": "' + COMMAND + '",' \
                       ' "_response_status": "COMPLETE",' \
                       ' "v": "2"' \
                       '}'
