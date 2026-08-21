"""Injectable time.

Sampling code that calls :func:`time.monotonic` directly cannot be tested, and a
measurement you cannot replay is an anecdote. Everything that needs the passage
of time takes a :class:`Clock`.
"""

from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    def monotonic(self) -> float:
        """Seconds from an arbitrary origin, never going backwards."""

    def sleep(self, seconds: float) -> None:
        """Block for approximately ``seconds``."""


class SystemClock:
    """The real one."""

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class ManualClock:
    """A clock that only moves when a test moves it.

    ``sleep`` advances the clock instead of blocking, so a one-hour soak test
    runs in microseconds and produces exactly the sample timestamps the real run
    would have produced at a perfect sample rate.
    """

    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)

    def monotonic(self) -> float:
        return self._now

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            self._now += float(seconds)

    def advance(self, seconds: float) -> None:
        self._now += float(seconds)
