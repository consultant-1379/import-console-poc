import logging
from logging import (Formatter, StreamHandler, BASIC_FORMAT)


def init_logger():
    """
    Initializes the module's logger if required.

    Python's root logger can be initialized by the user calling logging.basicConfig().

    In case root logger is NOT initialized, a default stream handler has to be added to the module's logger
    to avoid "No handlers could be found for logger" message.
    """
    if not __is_initialized(__module_root_logger()):
        if not __is_initialized(logging.getLogger()):  # root logger
            __module_root_logger().addHandler(__default_stream_handler())


def __module_root_logger():
    return logging.getLogger(__name__.split('.')[0])  # enmscripting


def __default_stream_handler():
    handler = StreamHandler()
    handler.setFormatter(Formatter(BASIC_FORMAT, None))
    return handler


def __is_initialized(logger):
    """
    Checks if the logger is initialized or not.

    Logger is initialized if there are associated handlers.
    """
    return len(logger.handlers) > 0
