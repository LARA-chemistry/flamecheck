"""
_____________________________________________________________________.

:PROJECT: Lab Data Reader

* logger *

:details: logger.
          s. [Advanced logging in python](https://arjancodes.com/blog/advanced-python-logging-configuration-techniques/)
________________________________________________________________________
"""

import logging
from typing import ClassVar

# _log_format = f"%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s"  # noqa: E501
_log_format = f"%(asctime)s [%(levelname)s] (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s"  # noqa: E501, F541
_log_format_stream = f"%(asctime)s [%(levelname)s] (%(filename)s).%(funcName)s(%(lineno)d):\n\t%(message)s"  # noqa: E501, F541


class CustomFilter(logging.Filter):
    """Custom filter to add color to log messages based on their level."""

    COLOR: ClassVar[dict[str, str]] = {
        "DEBUG": "GREEN",
        "INFO": "GREEN",
        "WARNING": "YELLOW",
        "ERROR": "RED",
        "CRITICAL": "RED",
    }

    def filter(self, record):
        """Filter method to add color to log records."""
        record.color = CustomFilter.COLOR[record.levelname]
        return True


def get_file_handler():
    """Create a file handler for logging."""
    file_handler = logging.FileHandler("lab_data_reader.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_log_format_stream))
    return file_handler


def get_stream_handler():
    """Create a stream handler for logging."""
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter(_log_format_stream))
    return stream_handler


def get_logger(name):
    """Get a logger with the specified name."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(get_file_handler())

    logger.addHandler(get_stream_handler())
    logger.addFilter(CustomFilter())
    return logger
