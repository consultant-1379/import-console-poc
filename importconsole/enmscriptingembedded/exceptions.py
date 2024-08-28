class EnmCmdException(Exception):
    """Root exception class"""


class TimeoutException(EnmCmdException):
    """Indicates that the command execution timed out"""


class IllegalStateException(EnmCmdException):
    """Indicates that an object is in an illegal state to process"""


class InternalError(EnmCmdException):
    """Indicates that an InternalError occurred. This could happen for example if the server response is invalid."""


class ConfigurationError(EnmCmdException):
    """Indicates that a configuration error occurred. This could include configuration
    outside ENM Scripting or Python, e.g., an invalid environment variable"""


class SessionTimeoutException(EnmCmdException):
    """Indicates that the user session has expired due to either the ENM Idle Timeout
    or the ENM Session Timeout having been passed"""
