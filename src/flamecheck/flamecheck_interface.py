"""
____________________________________________________________________.

:PROJECT: 

* Main module formal interface. *

:details: In larger projects, formal interfaces are helping to define
          a trustable contract.
          Currently there are two commonly used approaches:
          [ABCMetadata](https://docs.python.org/3/library/abc.html) or [Python Protocols](https://peps.python.org/pep-0544/)

       see also:
       ABC metaclass
         - https://realpython.com/python-interface/
         - https://dev.to/meseta/factories-abstract-base-classes-and-python-s-new-protocols-structural-subtyping-20bm

.. note:: -
.. todo:: -
________________________________________________________________________
"""


from abc import ABC, abstractmethod


class GreeterInterface(ABC):
    """
    Greeter formal Interface.

    TODO: test, if ABC baseclass is working as expected.
    """

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        """Check if subclass implements the greet_the_world method."""
        return (
            (hasattr(subclass, 'greet_the_world') 
            and callable(subclass.greet_the_world)) 
            or NotImplemented
        )


    @classmethod
    @abstractmethod
    def greet_the_world(self, name: str) -> str:
        """
        Greeting module - adds a name to a greeting.

        :param name: person to greet
        :type name: str
        """

