"""Turning a pile of samples into figures somebody can defend.

Two rules run through this module.

**Integrate, do not average.** Energy is the integral of power over time, and
the interval between samples is whatever the instrument actually managed, not
what it was asked for. Multiplying a mean wattage by a wall-clock duration is
the standard way to be quietly wrong by several percent whenever the sampler
stutters — which it does, under exactly the sustained load the run is meant to
characterise.

**Carry the uncertainty.** Every figure leaves this module with an error bar
derived from the instrument's rated accuracy and resolution. A joule figure
without one invites a comparison between two boards that differ by less than the
meter can see.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .errors import InsufficientSamples
from .instruments.base import InstrumentIdentity, Sample


@dataclass(frozen=True, slots=True)
class EnergyResult:
    """Energy over a window, with the error bar that makes it comparable."""

    joules: float
    joules_uncertainty: float
    mean_watts: float
    peak_watts: float
    min_watts: float
    duration_s: float
    sample_count: int
    #: Largest gap between consecutive samples. A gap far above the nominal
    #: sampling interval means the sampler was starved and the integral is
    #: interpolating across a period nobody observed.
    max_gap_s: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "joules": self.joules,
            "joules_uncertainty": self.joules_uncertainty,
            "mean_watts": self.mean_watts,
            "peak_watts": self.peak_watts,
            "min_watts": self.min_watts,
            "duration_s": self.duration_s,
            "sample_count": self.sample_count,
            "max_gap_s": self.max_gap_s,
        }


@dataclass(frozen=True, slots=True)
class LatencySummary:
    """Percentiles, because a mean latency hides the behaviour that gets noticed."""

    count: int
    mean_s: float
    min_s: float
    p50_s: float
    p90_s: float
    p95_s: float
    p99_s: float
    max_s: float
    stdev_s: float

    @classmethod
    def from_latencies(cls, latencies: Sequence[float]) -> LatencySummary:
        if len(latencies) < 2:
            raise InsufficientSamples(len(latencies), 2, "latency summary")
        ordered = sorted(latencies)
        return cls(
            count=len(ordered),
            mean_s=statistics.fmean(ordered),
            min_s=ordered[0],
            p50_s=_percentile(ordered, 0.50),
            p90_s=_percentile(ordered, 0.90),
            p95_s=_percentile(ordered, 0.95),
            p99_s=_percentile(ordered, 0.99),
            max_s=ordered[-1],
            stdev_s=statistics.pstdev(ordered),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "mean_s": self.mean_s,
            "min_s": self.min_s,
            "p50_s": self.p50_s,
            "p90_s": self.p90_s,
            "p95_s": self.p95_s,
            "p99_s": self.p99_s,
            "max_s": self.max_s,
            "stdev_s": self.stdev_s,
        }


def _percentile(ordered: Sequence[float], q: float) -> float:
    """Nearest-rank percentile on an already-sorted sequence.

    Nearest-rank rather than interpolated: every reported percentile is a
    latency that actually occurred, which is easier to defend in a report than
    a weighted average of two that did not.
    """
    if not ordered:
        raise InsufficientSamples(0, 1, "percentile")
    rank = max(1, min(len(ordered), int(q * len(ordered) + 0.9999999)))
    return ordered[rank - 1]


def integrate_energy(
    samples: Sequence[Sample], identity: InstrumentIdentity | None = None
) -> EnergyResult:
    """Trapezoidal integration of instantaneous power over the sample timestamps."""
    if len(samples) < 2:
        raise InsufficientSamples(len(samples), 2, "energy integration")

    joules = 0.0
    max_gap = 0.0
    powers = [s.watts for s in samples]
    for prev, cur, p_prev, p_cur in zip(samples, samples[1:], powers, powers[1:], strict=False):
        dt = cur.t_s - prev.t_s
        if dt < 0:
            raise ValueError(
                "sample timestamps went backwards; the sampler used a "
                "non-monotonic clock and the integral is meaningless"
            )
        max_gap = max(max_gap, dt)
        joules += 0.5 * (p_prev + p_cur) * dt

    duration = samples[-1].t_s - samples[0].t_s
    mean_w = joules / duration if duration > 0 else 0.0

    accuracy = identity.accuracy_pct / 100.0 if identity else 0.0
    resolution = identity.resolution_a if identity else 0.0
    mean_v = statistics.fmean([s.volts for s in samples])
    # Two independent contributions: a proportional term from rated accuracy,
    # and an absolute floor from what the instrument cannot resolve at all.
    uncertainty = joules * accuracy + resolution * mean_v * duration

    return EnergyResult(
        joules=joules,
        joules_uncertainty=uncertainty,
        mean_watts=mean_w,
        peak_watts=max(powers),
        min_watts=min(powers),
        duration_s=duration,
        sample_count=len(samples),
        max_gap_s=max_gap,
    )


def energy_above_idle(active: EnergyResult, idle_watts: float) -> tuple[float, float]:
    """Marginal energy of the work itself, with its uncertainty.

    A board that draws 2 W doing nothing and 2.4 W under load spends most of its
    energy being switched on. For a per-action figure, the idle floor belongs to
    the duty cycle, not to the action — subtracting it is what makes two boards
    with different idle draw comparable on the work they do.
    """
    marginal = max(0.0, active.joules - idle_watts * active.duration_s)
    return marginal, active.joules_uncertainty
