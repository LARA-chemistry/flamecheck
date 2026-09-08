"""
_____________________________________________________________________.

:PROJECT: 

* Main module implementation *

:details:  Main module implementation.

.. note:: -
.. todo:: -
________________________________________________________________________
"""


import logging

from flamecheck.flamecheck_interface import GreeterInterface

logger = logging.getLogger()


class HelloWorld(GreeterInterface):
    """
    HelloWorld class implementing the GreeterInterface.

    This class provides a simple greeting functionality.
    """

    def __init__(self) -> None:
        """Implementation of the GreeterInterface."""
 
    @classmethod
    def greet_the_world(self, name: str) -> str:
        """
        Greeting module - adds a name to a greeting.

        :param name: person to greet
        :type name: str
        """
        logger.debug(f"Greeting: {name}")
        return f"Hello world, {name} !"

