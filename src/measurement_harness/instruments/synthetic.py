"""A synthetic instrument, so the pipeline can be exercised with nothing on the bench.

This exists for the same reason the simulated cell exists in a governance
project: waiting for hardware produces software shaped by whatever the first
board made easy. It is emphatically not a model of any real device, and it says
so, its identity carries ``provenance="synthetic"``, which
:mod:`~measurement_harness.energy_model` refuses to convert into a downstream
figure unless the caller asks for it in as many words.

The generator is deterministic given a seed. Two runs of the same profile
produce byte-identical reports, which is what makes the report format testable.

It models an **averaging** instrument: each reading is the mean current since the
previous reading, weighted by how much of that interval the device spent loaded.
That is what a shunt monitor with a multi-sample averaging window actually
reports, and it is what lets an inline sampler (which by construction never
reads during a unit of work) still produce a defensible energy integral here.
No such luck on real hardware, which is why :class:`~..session.ThreadedSampler`
exists.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from ..clock import Clock, SystemClock
from .base import InstrumentIdentity, Sample


@dataclass(frozen=True, slots=True)
class SyntheticProfile:
    """Knobs describing a plausible shape, not a particular device.

    ``thermal_droop_pct_per_min`` is the one that matters: it is how the harness
    rehearses a sustained-load current profile that drifts, so the throttle
    detector has something to detect before any real part is warm.
    """

    idle_a: float = 0.12
    active_a: float = 0.48
    volts: float = 5.0
    #: Peak-to-peak white noise on current, in amps.
    noise_a: float = 0.01
    #: Mains-frequency-ish ripple, to keep integration honest about aliasing.
    ripple_a: float = 0.004
    ripple_hz: float = 50.0
    #: Current drift under sustained load, as a percentage of active draw.
    thermal_droop_pct_per_min: float = 0.0
    #: Rail sag at full load, in volts.
    sag_v: float = 0.0
    settings: dict[str, float] = field(default_factory=dict)


class SyntheticInstrument:
    """Deterministic generator satisfying :class:`~.base.Instrument`.

    ``duty`` is set by the session as the workload runs: 0.0 while idle, 1.0
    while an inference is in flight. Nothing here knows what a workload is.
    """

    def __init__(
        self,
        profile: SyntheticProfile | None = None,
        seed: int = 0,
        clock: Clock | None = None,
    ) -> None:
        self.profile = profile or SyntheticProfile()
        self._seed = seed
        # nosec B311, a seeded Mersenne Twister is exactly what is wanted here.
        # This generator produces measurement *noise* for a source that is
        # labelled synthetic and refused downstream; reproducibility from a seed
        # is the requirement, and unpredictability would defeat it.
        self._rng = random.Random(seed)  # nosec B311
        self._clock = clock or SystemClock()
        self._duty = 0.0
        self._mark = 0.0
        self._busy_s = 0.0
        self._interval_s = 0.0
        self._open = False

    # ------------------------------------------------------------------ driving
    def set_duty(self, duty: float) -> None:
        """0.0 idle, 1.0 fully loaded. The session drives this on every transition."""
        self._accrue()
        self._duty = max(0.0, min(1.0, float(duty)))

    def _accrue(self) -> None:
        now = self._clock.monotonic()
        span = max(0.0, now - self._mark)
        self._busy_s += span * self._duty
        self._interval_s += span
        self._mark = now

    # -------------------------------------------------------------- instrument
    def identity(self) -> InstrumentIdentity:
        return InstrumentIdentity(
            kind="synthetic",
            description=(
                "Deterministic synthetic source. Produces a plausible current "
                "shape for pipeline testing; models no real device."
            ),
            provenance="synthetic",
            accuracy_pct=0.0,
            resolution_a=0.0,
            sample_rate_hz=0.0,
            settings={"seed": self._seed, **dict(self.profile.settings)},
        )

    def open(self) -> None:
        self._open = True
        self._rng = random.Random(self._seed)  # nosec B311, see __init__
        self._mark = self._clock.monotonic()
        self._busy_s = 0.0
        self._interval_s = 0.0

    def read(self, t_s: float) -> Sample:
        if not self._open:
            from ..errors import InstrumentNotPresent

            raise InstrumentNotPresent("synthetic", "read() before open()")
        self._accrue()
        duty = self._busy_s / self._interval_s if self._interval_s > 0 else self._duty
        self._busy_s = 0.0
        self._interval_s = 0.0
        p = self.profile
        base = p.idle_a + (p.active_a - p.idle_a) * duty
        droop = 1.0 + (p.thermal_droop_pct_per_min / 100.0) * (t_s / 60.0)
        ripple = p.ripple_a * math.sin(2.0 * math.pi * p.ripple_hz * t_s)
        noise = self._rng.uniform(-p.noise_a / 2.0, p.noise_a / 2.0)
        amps = max(0.0, base * droop + ripple + noise)
        volts = p.volts - p.sag_v * duty
        return Sample(t_s=t_s, volts=volts, amps=amps)

    def close(self) -> None:
        self._open = False
