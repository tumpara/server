import abc
from dataclasses import dataclass
from typing import Generator, Literal, Optional


@dataclass
class BaseEvent(abc.ABC):
    """Base class for file events."""

    @abc.abstractmethod
    def commit(self, library: "storage.models.Library", **kwargs):
        """Handle this event for a given library."""
        raise NotImplementedError(
            "subclasses of BaseEvent must provide a handle() method"
        )


EventGenerator = Generator[BaseEvent, Optional[Literal[False]], None]
