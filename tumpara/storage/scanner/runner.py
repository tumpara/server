import logging
import multiprocessing
import os
from typing import Iterator

from django.conf import settings
from django.db import connection, transaction

from ..models import Library
from . import BaseEvent, EventGenerator

__all__ = ["run"]
_logger = logging.getLogger(__name__)


def run(
    library: Library,
    events: EventGenerator,
    *,
    thread_count: int = None,
    **kwargs,
):  # pragma: no cover
    """Handle scanner events for a library, automatically determining

    :param library: The library that is currently being scanned.
    :param events: Generator that provides scanner events.
    :param thread_count: Number of processes to launch. Setting this to `None` will
        use 90% of available CPUs. This parameter may be ignored under certain
        circumstances to avoid concurrency issues (currently these cases are when using
        SQLite or CUDA). Setting this to 1 disables concurrency completely.
    :param kwargs: Additional flags that will be passed on to event handlers.
    """
    if thread_count is None:
        thread_count = max(1, int(os.cpu_count() * 0.9))
    elif not isinstance(thread_count, int):
        raise TypeError("thread_count must be an integer")
    elif thread_count < 1:
        raise ValueError("thread_count must be at least 1")

    if (
        connection.settings_dict["ENGINE"]
        in ["django.db.backends.sqlite3", "django.contrib.gis.db.backends.spatialite"]
        and thread_count != 1
    ):
        _logger.warning(
            f"Ignoring requested thread count of {thread_count} to avoid concurrency "
            f"issues with the SQLite backend."
        )
        thread_count = 1
    else:
        try:
            import dlib

            if dlib.DLIB_USE_CUDA and thread_count != 1:
                _logger.warning(
                    f"Ignoring requested thread count of {thread_count} because CUDA "
                    f"is active."
                )
                thread_count = 1
        except ImportError:
            pass

    if thread_count == 1:
        return run_sequential(library, events, **kwargs)

    _logger.info(
        f"Handling scanner events for library {library} with {thread_count} workers."
    )

    # Spawn the requested number of worker processes and initialize the queue.
    context = multiprocessing.get_context("spawn")
    queue = context.JoinableQueue(maxsize=2 * thread_count)
    counter = context.Value("i", 0)

    # Close the active database connection as this can cause issues with
    # multiprocessing. See here for details: https://stackoverflow.com/a/10684672
    connection.close()

    from .worker import process

    workers = []
    for _ in range(thread_count):
        worker = context.Process(
            target=process,
            args=(library.id, queue, counter, kwargs),
            daemon=True,
        )
        workers.append(worker)
        worker.start()

    while True:
        try:
            event = next(events)
            if event is None:
                continue
            queue.put(event)
        except StopIteration:
            break

    _logger.debug("Received last event. Waiting for handlers to finish...")
    queue.join()
    _logger.info(f"Finished event handling for {library}.")


def run_sequential(library: Library, events: Iterator[BaseEvent], **kwargs):
    """Handle scanner events for a library in a sequential manner (disable concurrency /
    multiprocessing).

    :see: :func:`run`
    """
    _logger.info(f"Sequentially handling scanner events for library {library}.")

    for index, event in enumerate(events):
        if event is None:
            continue

        with transaction.atomic():
            try:
                event.commit(library, **kwargs)
            except:  # noqa
                _logger.exception(f"Error while handling event of type {type(event)}.")

        if (
            index % settings.REPORT_INTERVAL == settings.REPORT_INTERVAL - 1
        ):  # pragma: no cover
            _logger.info(f"{index + 1} events processed so far.")
