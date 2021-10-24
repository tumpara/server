from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Generator, Literal, Optional

if TYPE_CHECKING:
    from ..models import Library


class Event(abc.ABC):
    """Base class for file events."""

    @abc.abstractmethod
    def commit(self, library: Library, **kwargs):
        """Handle this event for a given library."""
        raise NotImplementedError(
            "subclasses of BaseEvent must provide a commit() method"
        )


EventGenerator = Generator[Event, Optional[Literal[False]], None]
