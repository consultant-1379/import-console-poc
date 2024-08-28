#!/usr/bin/python -tt
import logging
import json
from ..exceptions import InternalError
from element import *

logger = logging.getLogger(__name__)


class Output(object):
    """
    Base class representing the output from a command
    """

    _OUTPUT = 'output'
    _COMMAND = 'command'
    _RESPONSE_STATUS = '_response_status'
    _VERSION = 'v'

    def __init__(self, http_code, success, json_response=None, handler=None):
        self._handler = handler
        self._http_response_code = http_code
        self._success = success
        self._parsed_json = None
        self._is_complete = False
        self._element_group_by_key = {}

        if success and json_response is not None:
            self._append_response(json_response)
        else:
            logger.debug('Output text is: %s', json_response)

    def http_response_code(self):
        """
        :return:                http_response code from the underlying request
        """
        return self._http_response_code

    def is_command_result_available(self):
        """
        :return:                boolean, true if the request was successfully sent to the ENM server
        """
        return self._success

    def is_complete(self):
        return self._is_complete

    def _append_response(self, json_text):
        if self._is_complete:
            raise InternalError('Illegal state, cannot add more to a completed response.')

        if json_text is not None:
            try:
                new_json = json.loads(json_text)
            except ValueError as ex:
                logger.warn('Illegal server response: response is not in JSON format')
                raise InternalError('Illegal server response: response is not in JSON format', ex)

            if self._parsed_json is None:
                self._parsed_json = {self._OUTPUT: {Element.KEY_TYPE: ElementGroup.TYPE, ElementGroup.KEY_ITEMS: []}}

            self._merge_to_parsed_json(new_json)

            self._check_if_response_complete_and_process()

    def _check_if_response_complete_and_process(self):
        self._is_complete = self._parsed_json.get(self._RESPONSE_STATUS, '') == 'COMPLETE'

        if self._is_complete:
            self._element_group_by_key = {}  # clear the cache, not needed anymore
            self._process_complete_json(self._parsed_json)

    def _process_complete_json(self, json):
        pass

    def _merge_to_parsed_json(self, new_json):
        if self._RESPONSE_STATUS in new_json:
            self._parsed_json[self._RESPONSE_STATUS] = new_json[self._RESPONSE_STATUS]

        if self._COMMAND in new_json:
            self._parsed_json[self._COMMAND] = new_json[self._COMMAND]

        if self._OUTPUT in new_json and ElementGroup.KEY_ITEMS in new_json[self._OUTPUT]:
            root_elements_list = Output._get_group_elements_list(self._parsed_json[self._OUTPUT])
            new_elements_list = Output._get_group_elements_list(new_json[self._OUTPUT])

            for element in new_elements_list:
                self._append_element_into_list(element, root_elements_list)

    def _append_element_into_list(self, element, element_list):

        if Output._is_group_element(element):
            append_target = None
            if ElementGroup.GROUP_KEY in element:
                group_key = Output._get_group_key(element)
                append_target = self._element_group_by_key.get(group_key)

            if append_target:
                target_list = Output._get_group_elements_list(append_target)
                for group_item in Output._get_group_elements_list(element):
                    self._append_element_into_list(group_item, target_list)
            else:
                element_list.append(element)
                self._update_element_group_by_key(element)
        else:
            element_list.append(element)

    def _update_element_group_by_key(self, element):

        if Output._is_group_element(element):
            group_key = Output._get_group_key(element)
            if group_key and group_key not in self._element_group_by_key:
                self._element_group_by_key[group_key] = element

            for child_element in Output._get_group_elements_list(element):
                self._update_element_group_by_key(child_element)

    def _error_if_not_completed(self):
        if not self._is_complete:
            raise InternalError('Illegal state, response is not completed yet.')

    @staticmethod
    def _is_group_element(element):
        return element[Element.KEY_TYPE] == ElementGroup.TYPE

    @staticmethod
    def _get_group_key(element):
        return element.get(ElementGroup.GROUP_KEY)

    @staticmethod
    def _get_group_elements_list(element):
        return element[ElementGroup.KEY_ITEMS]

    def _create_elements(self, output_json):
        """
        Recursive method to create the elements from the JSON.

        JSON contains elements. Each element can be an Element or GroupElement.
        Each GroupElement can contain Elements and GroupElements, therefore recursive parsing is required.
        """
        type = output_json[Element.KEY_TYPE]

        if type == TextElement.TYPE:
            # Leaf element
            return TextElement(output_json)
        elif type == FileElement.TYPE:
            # Leaf element
            return FileElement(output_json, self._handler)
        elif type == ElementGroup.TYPE:
            # Recursive call with each item
            items = map(lambda e: self._create_elements(e), output_json[ElementGroup.KEY_ITEMS])
            output_json[ElementGroup.KEY_ITEMS] = items
            group = ElementGroup(output_json)
            return group
        else:
            # New DTO
            return Element(output_json)


class OutputFactory(object):
    """
    Base class for instantiating an instance of Output
    """

    def __init__(self):
        pass

    def create_output(self, http_code, success, json_response=None, handler=None):
        pass
