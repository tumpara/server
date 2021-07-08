from __future__ import annotations

import logging
import multiprocessing

import django
from django.conf import settings
from django.db import connection, transaction

from . import BaseEvent

__all__ = ["worker"]
_logger = logging.getLogger(__name__)


def process(
    library_pk: int,
    queue: multiprocessing.JoinableQueue,
    counter: multiprocessing.Value,
    kwargs,
):  # pragma: no cover
    """Worker process for multiprocessed event handling.

    :param library_pk: ID of the library that is currently being scanned.
    :param queue: Queue to receive scanner events.
    :param counter: Counter value used to report back how many events have been handled.
    :param kwargs: Additional flags that will be passed on to event handlers.
    """

    # Call django.setup here because this worker is run in a standalone process. The
    # imports are delayed until here because they require the setup call beforehand.
    django.setup()
    from ..models import Library

    library = Library.objects.get(pk=library_pk)

    try:
        while True:
            event: BaseEvent = queue.get()

            with transaction.atomic():
                try:
                    event.commit(library, **kwargs)
                except:  # noqa
                    try:
                        event_path = event.path
                    except AttributeError:
                        try:
                            event_path = event.new_path
                        except AttributeError:
                            event_path = None

                    _logger.exception(
                        f"Error while handling event of type {type(event)}"
                        + (
                            f" for path {event_path!r}"
                            if event_path is not None
                            else ""
                        )
                        + "."
                    )

            with counter.get_lock():
                counter.value += 1
                if counter.value % settings.REPORT_INTERVAL == 0 and counter.value > 0:
                    _logger.info(f"{counter.value} events processed so far.")

            queue.task_done()
    finally:
        connection.close()
