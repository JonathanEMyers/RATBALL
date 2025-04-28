"""
Lock-free (GIL-protected) single-producer / single-consumer buffers.
"Lock-free" here means **no user-code locks**; CPython’s
GIL guarantees atomic pointer updates, and `threading.Condition`
handles the occasional wait without busy-spinning.

Usage
-----
buffer = DoubleBuffer[Frame](capacity=900)     # 30 fps × 30 s
producer.put(frame)                            # non-blocking
if buffer.ready():                             # consumer side
    for f in buffer.drain():
        socket_writer.send(f.pack())
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable
from typing import Generic, List, Optional, TypeVar

T = TypeVar("T")


# RingBuffer is a primitive buffer used in implementing the DoubleBuffer type
class RingBuffer(Generic[T]):
    """SPSC ring with optional blocking semantics.

    Parameters
    ----------
    capacity : int
        Maximum number of elements held at once.  Must be > 0.
    """

    __slots__ = (
        "_capacity",
        "_buffer",
        "_head",
        "_tail",
        "_size",
        "_not_empty",
        "_not_full",
    )

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")

        self._capacity: int = capacity
        self._buffer: List[Optional[T]] = [None] * capacity
        self._head: int = 0  # next write slot
        self._tail: int = 0  # next read slot
        self._size: int = 0

        # Conditions piggy-back on the GIL; they only park the thread
        # when the buffer is empty/full, so no user-visible locks.
        self._not_empty = threading.Condition()
        self._not_full = threading.Condition()

    # ------------------------------------------------------------------ put

    def put(self, item: T, block: bool = True, timeout: Optional[float] = None) -> None:
        """Insert *item*; optionally block until space is available."""
        with self._not_full:
            if not block and self._size == self._capacity:
                raise BufferError("ring buffer full")

            start = time.monotonic()
            while self._size == self._capacity:
                if timeout is not None:
                    remaining = timeout - (time.monotonic() - start)
                    if remaining <= 0 or not self._not_full.wait(remaining):
                        raise TimeoutError("ring put() timed-out")
                else:
                    self._not_full.wait()

            self._buffer[self._head] = item
            self._head = (self._head + 1) % self._capacity
            self._size += 1

            # Wake up reader if it was waiting.
            with self._not_empty:
                self._not_empty.notify()

    # ------------------------------------------------------------------ get

    def get(self, block: bool = True, timeout: Optional[float] = None) -> T:
        """Remove and return next element; block if empty when *block* is True."""
        with self._not_empty:
            if not block and self._size == 0:
                raise BufferError("ring buffer empty")

            start = time.monotonic()
            while self._size == 0:
                if timeout is not None:
                    remaining = timeout - (time.monotonic() - start)
                    if remaining <= 0 or not self._not_empty.wait(remaining):
                        raise TimeoutError("ring get() timed-out")
                else:
                    self._not_empty.wait()

            item = self._buffer[self._tail]
            # Help GC & debugging:
            self._buffer[self._tail] = None
            self._tail = (self._tail + 1) % self._capacity
            self._size -= 1

            # Wake one producer if it was blocked.
            with self._not_full:
                self._not_full.notify()

            return item  # type: ignore[return-value]

    # -------------------------------------------------------------- helpers

    def __len__(self) -> int:
        return self._size

    @property
    def full(self) -> bool:
        return self._size == self._capacity

    @property
    def empty(self) -> bool:
        return self._size == 0


# ---------------------------------------------------------------------------
#                            Double-buffer façade
# ---------------------------------------------------------------------------


class DoubleBuffer(Generic[T]):
    """Two-ring swap buffer: write to *front*, read from *back*.

    When *front* fills (`put()` raises ``BufferError``) call
    :pymeth:`swap()`; the previous *front* becomes the new *back*, ready
    for draining, and the producer continues unblocked.
    """

    __slots__ = ("_front", "_back", "_swap_lock")

    def __init__(self, capacity: int) -> None:
        self._front: RingBuffer[T] = RingBuffer(capacity)
        self._back: RingBuffer[T] = RingBuffer(capacity)
        # Single swap at a time – extremely short-lived critical section.
        self._swap_lock = threading.Lock()

    # ----------------------------------------------------------- producer API

    def put(self, item: T, *, drop_if_full: bool = False) -> None:
        """Attempt to enqueue *item*.

        If *front* is full:
            * If *drop_if_full* is True – silently drop the frame.
            * Otherwise – swap buffers then insert (may still raise BufferError
              if the new front _also_ happens to be full, which indicates the
              consumer is stalled).
        """
        try:
            self._front.put(item, block=False)
        except BufferError:
            if drop_if_full:
                return
            self.swap()
            self._front.put(item, block=False)

    # ---------------------------------------------------------- consumer API

    def ready(self) -> bool:
        """True when *back* holds at least one element."""
        return not self._back.empty

    def drain(self) -> Iterable[T]:
        """Yield all elements currently in *back*."""
        while not self._back.empty:
            try:
                yield self._back.get(block=False)
            except BufferError:  # concurrent producer swapped again
                break

    def pop(self) -> T:
        if not self._back.empty:
            try:
                return self._back.get()
            except BufferError:
                pass

    # ------------------------------------------------------------- internal

    def swap(self) -> None:
        """Atomically flip front/back rings."""
        with self._swap_lock:
            self._front, self._back = self._back, self._front

    # --------------------------------------------------------------- stats

    def __len__(self) -> int:
        """Total elements across both rings (mostly for debugging)."""
        return len(self._front) + len(self._back)
