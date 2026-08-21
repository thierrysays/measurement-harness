"""Detecting the thing a one-shot benchmark cannot see.

Sustained inference on a passively-cooled board does not fail; it slows down.
The SoC reaches its thermal limit, the governor pulls the clock back, throughput
falls, and every published figure taken in the first thirty seconds becomes
wrong for the deployment. That gap — burst performance against steady-state
performance — is the single most useful number this harness produces, and it is
the one almost never quoted.

The detector is deliberately crude and deliberately explicit. Split the run into
equal windows, compute throughput in each, and compare the last sustained window
against the first. A regression beyond the threshold, *persisting* rather than
appearing once, is a throttle. One slow window is a neighbour's microwave.

What this cannot do: distinguish thermal throttling from any other cause of
sustained slowdown — memory pressure, a background update, a power supply that
sags as it warms. The verdict says *throughput regressed*, and names temperature
as evidence only when the device under test supplied a temperature series.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Window:
    """One slice of a sustained run."""

    index: int
    start_s: float
    end_s: float
    operations: int
    mean_watts: float
    mean_latency_s: float
    max_temperature_c: float | None = None

    @property
    def throughput_ops_s(self) -> float:
        span = self.end_s - self.start_s
        return self.operations / span if span > 0 else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "operations": self.operations,
            "throughput_ops_s": self.throughput_ops_s,
            "mean_watts": self.mean_watts,
            "mean_latency_s": self.mean_latency_s,
            "max_temperature_c": self.max_temperature_c,
        }


@dataclass(frozen=True, slots=True)
class ThrottleVerdict:
    """Did sustained throughput hold, and if not, from when."""

    throttled: bool
    #: Fractional loss from the first window to the mean of the sustained tail.
    regression: float
    threshold: float
    #: Run-relative time of the first window that stayed below threshold.
    onset_s: float | None
    first_window_ops_s: float
    sustained_ops_s: float
    #: Temperature rise across the run, when the device supplied one.
    temperature_rise_c: float | None
    #: Stated in the artefact so a reader is not left to infer it.
    caveat: str = (
        "throughput regression is observed, not attributed; thermal throttling is "
        "one cause among several unless a temperature series is present"
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "throttled": self.throttled,
            "regression": self.regression,
            "threshold": self.threshold,
            "onset_s": self.onset_s,
            "first_window_ops_s": self.first_window_ops_s,
            "sustained_ops_s": self.sustained_ops_s,
            "temperature_rise_c": self.temperature_rise_c,
            "caveat": self.caveat,
        }


def assess_throttling(
    windows: Sequence[Window],
    threshold: float = 0.05,
    consecutive: int = 2,
) -> ThrottleVerdict:
    """Compare the sustained tail against the opening window.

    ``consecutive`` is the anti-noise rule: a window must be followed by that
    many further windows also below threshold before its start counts as the
    onset. Without it, any single stalled window in a long run reads as a
    throttle, and the detector becomes an expensive way to detect scheduling.
    """
    if len(windows) < 2:
        raise ValueError("throttle assessment needs at least two windows")

    first = windows[0]
    tail = windows[1:]
    first_rate = first.throughput_ops_s
    sustained_rate = (
        sum(w.throughput_ops_s for w in tail) / len(tail) if tail else first_rate
    )
    regression = (
        (first_rate - sustained_rate) / first_rate if first_rate > 0 else 0.0
    )

    onset: float | None = None
    for i, w in enumerate(tail):
        below = first_rate > 0 and (first_rate - w.throughput_ops_s) / first_rate > threshold
        if not below:
            continue
        run = tail[i : i + consecutive]
        if len(run) == consecutive and all(
            (first_rate - x.throughput_ops_s) / first_rate > threshold for x in run
        ):
            onset = w.start_s
            break

    temps = [w.max_temperature_c for w in windows if w.max_temperature_c is not None]
    rise = (max(temps) - temps[0]) if len(temps) >= 2 else None

    return ThrottleVerdict(
        throttled=onset is not None and regression > threshold,
        regression=regression,
        threshold=threshold,
        onset_s=onset,
        first_window_ops_s=first_rate,
        sustained_ops_s=sustained_rate,
        temperature_rise_c=rise,
    )
