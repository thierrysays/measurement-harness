"""What the device is asked to do while it is being measured.

A workload here is anything with a unit of work that can be invoked repeatedly:
one inference, one frame, one classification, one control loop iteration. The
harness times each invocation and integrates power across the whole run. It does
not know or care whether the work is a vision model, a Kalman filter, or a busy
loop, which is what keeps the harness device-agnostic.

Sustained load is the point. A single inference tells you almost nothing that
matters operationally: the interesting figures are what happens in minute four,
when the SoC is warm, the fan curve has moved, and the clock has been pulled
back. So :class:`Workload` is invoked in a loop, not once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .clock import Clock, SystemClock


@runtime_checkable
class Workload(Protocol):
    """Prepare once, invoke many times, tear down once."""

    def name(self) -> str:
        """Stable identifier recorded in the report."""

    def describe(self) -> dict[str, Any]:
        """Everything needed to reproduce this workload: model, input, batch."""

    def prepare(self) -> None:
        """Load the model, warm the caches, allocate the buffers."""

    def invoke(self) -> None:
        """Perform exactly one unit of work. The harness times this call."""

    def teardown(self) -> None:
        """Release whatever ``prepare`` acquired. Safe to call twice."""


@dataclass
class SyntheticWorkload:
    """A workload with a known latency, for testing the harness itself.

    ``thermal_slowdown_pct_per_min`` makes invocations get slower as the run
    proceeds. That is how the throttle detector is tested without heating
    anything: the expected verdict is known in advance, which is the only way to
    know the detector is measuring drift rather than noise.
    """

    latency_s: float = 0.020
    jitter_s: float = 0.0
    thermal_slowdown_pct_per_min: float = 0.0
    model: str = "synthetic/none"
    input_shape: str = "n/a"
    #: Injected so a one-hour soak test runs in microseconds under a ManualClock.
    clock: Clock = field(default_factory=SystemClock)
    _started_at: float = field(default=0.0, init=False, repr=False)
    _n: int = field(default=0, init=False, repr=False)

    def name(self) -> str:
        return "synthetic"

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "synthetic",
            "model": self.model,
            "input_shape": self.input_shape,
            "nominal_latency_s": self.latency_s,
            "thermal_slowdown_pct_per_min": self.thermal_slowdown_pct_per_min,
        }

    def prepare(self) -> None:
        self._started_at = self.clock.monotonic()
        self._n = 0

    def latency_at(self, t_s: float) -> float:
        """Latency this invocation would take at run-relative time ``t_s``."""
        drift = 1.0 + (self.thermal_slowdown_pct_per_min / 100.0) * (t_s / 60.0)
        wobble = self.jitter_s * (0.5 if self._n % 2 else -0.5)
        return max(1e-9, self.latency_s * drift + wobble)

    def invoke(self) -> None:
        """Consume the latency this invocation would have taken.

        Under a :class:`~.clock.ManualClock` this advances simulated time rather
        than blocking, which is what lets a soak test with a known expected
        verdict run inside the unit suite.
        """
        t_s = self.clock.monotonic() - self._started_at
        self.clock.sleep(self.latency_at(t_s))
        self._n += 1

    def teardown(self) -> None:
        return None
