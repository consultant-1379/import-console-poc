#!/usr/bin/python -tt
import copy
from file import FileResult


class Element(object):
    """
    Element represents a generic element returned from an ENM command
    """
    KEY_LABELS = '_label'
    KEY_TYPE = 'type'

    # Make sure instances of this class remaining immutable.
    # Don't override __new__(), because ElementGroup depends on it for inheritance.
    def __init__(self, attributes={}):
        self._attributes = attributes
        self._attributes_cache = None

        # Default values
        if Element.KEY_LABELS not in self._attributes.keys():
            attributes[Element.KEY_LABELS] = ()
        else:
            attributes[Element.KEY_LABELS] = tuple(attributes[Element.KEY_LABELS])

    def labels(self):
        """
        :return tuple: Labels in a tuple
        """
        return self._attributes[self.KEY_LABELS]

    def attributes(self):
        """
        :return dict: Element attributes as a dict
        """
        return copy.deepcopy(self._pub_attributes())

    def _pub_attributes(self):
        if self._attributes_cache is None:
            self._attributes_cache = dict(filter(lambda kv: not kv[0].startswith('_'), self._attributes.items()))
        return self._attributes_cache

    @classmethod
    def _get_attributes(cls, type, labels=[]):
        attributes = dict()
        attributes[Element.KEY_TYPE] = type
        attributes[Element.KEY_LABELS] = labels
        return attributes


class TextElement(Element):
    """
    TextElement represents a text element returned from an ENM command which has a string value
    """
    KEY_VALUE = 'value'
    TYPE = 'text'

    # Make sure instances of this class remaining immutable.
    def __init__(self, attributes={}):
        super(TextElement, self).__init__(attributes)

        # Default values
        if TextElement.KEY_TYPE not in self._attributes.keys():
            self._attributes[Element.KEY_TYPE] = TextElement.TYPE

    def value(self):
        """
        :return string: value of the element
        """
        return self._attributes[TextElement.KEY_VALUE]

    def __repr__(self):
        return str(self.value())

    @classmethod
    def _get_attributes(cls, value, type=TYPE, labels=[]):
        attributes = Element._get_attributes(type, labels)
        attributes[TextElement.KEY_VALUE] = value
        return attributes


class ElementGroup(Element, tuple):
    """
    ElementGroup represents a group element returned from an ENM command which contains a list of elements.
    """
    KEY_ITEMS = '_elements'
    GROUP_KEY = '_group_key'
    TYPE = 'group'

    # Make sure instances of this class remaining immutable.
    def __new__(cls, arg={}):
        # In case calling constructor: ElementGroup(attributes)
        if type(arg) is dict:
            return tuple.__new__(cls, ElementGroup._get_items(arg))
        # In case of copy / deepcopy arg is a tuple: copy.deepcopy(element_group)
        else:
            return tuple.__new__(cls, arg)

    def __init__(self, attributes={}):
        super(ElementGroup, self).__init__(attributes)

        # Default values
        if ElementGroup.KEY_ITEMS not in self._attributes.keys():
            self._attributes[self.KEY_ITEMS] = list()

        if Element.KEY_TYPE not in self._attributes.keys():
            attributes[Element.KEY_TYPE] = ElementGroup.TYPE

        # Items are stored in 'list', no need to store two places
        self._attributes.pop(self.KEY_ITEMS)

        self._groups_cache = None

    def _has_group_key(self):
        if self._attributes.get(self.GROUP_KEY):
            return True
        return False

    def has_elements(self):
        """
        :return boolean: True if this group contains Elements
        """
        return len(self) > 0

    def has_groups(self):
        """
        :return boolean: True if this group contains ElementGroups
        """
        return len(self.groups()) > 0

    def groups(self):
        """
        Returns all of the group elements within this group

        :return ElementGroup: group of group elements within this group
        """
        if self._groups_cache is None:
            self._groups_cache = self._find_by_type(ElementGroup)
        return self._groups_cache

    def find_by_label(self, label):
        """
        Finds all of the elements in the groups with the specified label

        :param label: label to find
        :return ElementGroup: group of elements with a matching label
        """
        res = filter(lambda e: label in e.labels(), self)
        return ElementGroup(ElementGroup._get_attributes(items=res, labels=[label]))

    def _find_by_type(self, cls):
        """
        Finds all of the elements in the groups of the specified class

        :param cls: Class
        :return ElementGroup: group of elements of the specified class
        """
        res = filter(lambda e: type(e) is cls, self)
        return ElementGroup(ElementGroup._get_attributes(items=res, labels=[cls]))

    def _find_by_type_value(self, type_value):
        """
        Finds all of the elements in the groups of the specified type

        :param type_value: type
        :return ElementGroup: group of elements of the specified type
        """
        res = filter(lambda e: e.attributes()[Element.KEY_TYPE] == type_value, self)
        return ElementGroup(ElementGroup._get_attributes(items=res, labels=[type_value]))

    @classmethod
    def _get_attributes(cls, items=[], type=TYPE, labels=[]):
        attributes = Element._get_attributes(type, labels)
        attributes[ElementGroup.KEY_ITEMS] = items
        return attributes

    @classmethod
    def _get_items(cls, attributes={}):
        if ElementGroup.KEY_ITEMS not in attributes.keys():
            return []
        else:
            return attributes[ElementGroup.KEY_ITEMS]


class FileElement(Element, FileResult):
    """
    FileElement represents a file available for download

    This object can be used to download the file contents from ENM.
    """
    TYPE = 'attachment'

    KEY_FILE_ID = '_fileId'
    KEY_APP_ID = '_applicationId'
    KEY_NAME = 'name'

    # Make sure instances of this class remaining immutable.
    def __init__(self, attributes={}, handler=None):
        super(FileElement, self).__init__(attributes)

        # Default values
        if FileElement.KEY_NAME not in self._attributes.keys():
            self._attributes[self.KEY_NAME] = None

        FileResult.__init__(self,
                            self._attributes[self.KEY_APP_ID],
                            self._attributes[self.KEY_FILE_ID],
                            handler)

    def get_name(self):
        """
        Get the name of the file

        .. deprecated:: 1.11.1
        Deprecated since it can't reliably return the file name

        :return string: the name of the file
        """
        return self._attributes[self.KEY_NAME]
