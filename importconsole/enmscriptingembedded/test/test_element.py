from enmscripting import *
from enmscripting.command.command import CommandOutput
from .json_generator import *
import logging

logging.basicConfig()
logging.getLogger().setLevel(level=logging.DEBUG)


# Element

def test_element_attributes_empty():
    e = Element()
    assert 0 == len(e.attributes())
    assert 0 == len(e.labels())
    assert e.labels() == ()  # labels is a tuple


def test_element_attributes_not_empty():
    attributes = {"pub1": "pub1", "pub2": "pub2"}
    e = Element(attributes)

    assert len(e.attributes()) is 2

    assert 'pub1' in e.attributes().keys()
    assert 'pub2' in e.attributes().keys()
    assert 'pub1' == e.attributes()['pub1']
    assert 'pub2' == e.attributes()['pub2']


def test_element_attributes_private():
    priv = '_priv1'
    attributes = {"pub1": "pub1",
                  "pub2": "pub2",
                  priv: "_priv1"}

    e = Element(attributes)

    assert len(e.attributes()) is 2
    assert priv not in e.attributes().keys()


# Element is immutable

def test_element_attributes_immutable():
    attributes = {"pub1": "pub1",
                  "pub2": "pub2"}

    e = Element(attributes)
    get_att_1 = e.attributes()

    assert len(get_att_1) is 2, 'Lenght of attributes is [' + str(len(get_att_1)) + '], but expected [2]'

    del get_att_1['pub1']
    assert len(get_att_1) is 1

    assert len(e.attributes()) is 2, 'Lenght of attributes is [' + str(len(e.attributes())) + '], but expected [2]'

    get_att_2 = e.attributes()
    get_att_2['pub3'] = 'pub3'
    assert len(get_att_2) is 3

    assert len(e.attributes()) is 2, 'Lenght of attributes is [' + str(len(e.attributes())) + '], but expected [2]'


def test_element_attribute_values_immutable():
    attributes = {"pub1": "pub1",
                  "pub2": "pub2"}
    e = Element(attributes)

    orig_pub1 = e.attributes()['pub1']
    e.attributes()['pub1'] = 'new'
    assert e.attributes()['pub1'] is orig_pub1


def test_element_attribute_list_immutable():
    attributes = {"string": "pub1",
                  "list": [1, 2, 3]}
    e = Element(attributes)

    list1 = e.attributes()['list']
    orig_size = len(list1)

    list1.append(4)
    assert len(list1) is orig_size + 1
    assert len(e.attributes()['list']) is orig_size

    list2 = e.attributes()['list']
    list2.remove(2)
    assert len(list2) is orig_size - 1
    assert len(e.attributes()['list']) is orig_size


# TextElement

def test_create_empty_text_element():
    e = TextElement()
    assert type(e) is TextElement
    assert e.attributes()[Element.KEY_TYPE] is TextElement.TYPE


def test_create_text_element():
    attributes = TextElement._get_attributes('FDN : MeContext=LTE01ERBS00001')
    e = TextElement(attributes)
    assert type(e) is TextElement
    assert e.value() == 'FDN : MeContext=LTE01ERBS00001', \
        "Was expecting: FDN : MeContext=LTE01ERBS00001 but got : %s" % e.value()


def test_text_element_labels_empty():
    attributes = TextElement._get_attributes('FDN : MeContext=LTE01ERBS00001')
    e = TextElement(attributes)
    assert len(e.labels()) == 0


def test_text_element_labels():
    attributes = TextElement._get_attributes('FDN : MeContext=LTE01ERBS00001', labels=['label1', 'label2'])
    e = TextElement(attributes)
    assert len(e.labels()) is 2
    assert e.labels()[0] == 'label1'
    assert e.labels()[1] == 'label2'


# FileElement

def test_create_file_element():
    attributes = {FileElement.KEY_APP_ID: 1, FileElement.KEY_FILE_ID: 2}
    f = FileElement(attributes)

    assert f.attributes()[FileElement.KEY_NAME] is None
    assert f._attributes[FileElement.KEY_APP_ID] is 1
    assert f._attributes[FileElement.KEY_FILE_ID] is 2


def test_command_output_has_files_true():
    json = generate_json(5, 2, 3, 3, 3)
    cmd_output = CommandOutput(200, True, json)

    assert cmd_output.has_files()


def test_command_output_has_files_false():
    json = generate_json(5, 2, 3, 3, 0)
    cmd_output = CommandOutput(200, True, json)

    assert not cmd_output.has_files()


def test_command_output_files():
    json = generate_json(5, 2, 3, 3, 3)
    cmd_output = CommandOutput(200, True, json)

    assert 3 is len(cmd_output.files())

    first_file_name = cmd_output.files()[0].get_name()
    assert first_file_name.endswith("0")  # file_0
    last_file_name = cmd_output.files()[-1].get_name()
    assert last_file_name.endswith("2")  # file_2


# GroupElement

def test_group_element_deep_copy():
    e1 = Element()
    e2 = Element()
    group = ElementGroup(ElementGroup._get_attributes(items=[e1, e2]))

    assert len(group) is 2
    group_copied = copy.deepcopy(group)
    assert len(group_copied) is 2
