"""Running a measurement: idle baseline, sustained load, windowed throughout.

The shape of a run is fixed and short, because the arguments about methodology
should happen once, here, rather than differently in every benchmark script:

1. **Idle baseline first.** Without it, a per-operation energy figure includes
   whatever the board spends being switched on, and boards with different idle
   draw stop being comparable.
2. **Sustained load, in windows.** Not one inference, not thirty seconds. Long
   enough for the part to get warm, sliced into windows so the slowdown has
   somewhere to show up.
3. **Cool-down is not measured.** It varies with the room, and reporting it
   invites comparisons between benches rather than between devices.

Sampling strategy is pluggable for one reason: an inline sampler is exactly
reproducible and therefore testable, and a threaded sampler is what you need on
real hardware where an inference blocks for longer than the sample period. Both
are honest about which they are, and the report records it.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from .clock import Clock, SystemClock
from .instruments.base import Instrument, Sample
from .metrics import EnergyResult, LatencySummary, energy_above_idle, integrate_energy
from .thermal import ThrottleVerdict, Window, assess_throttling


@dataclass(frozen=True, slots=True)
class SessionSpec:
    """Everything that decides what a run means, in one diffable object."""

    #: Free-form identifier of the device under test. The harness never
    #: validates it, it is device-agnostic, and a hard-coded board list is the
    #: first step towards not being.
    device: str
    #: Seconds of idle sampling before the load starts.
    idle_s: float = 10.0
    #: Number of load windows.
    windows: int = 6
    #: Seconds per load window.
    window_s: float = 60.0
    #: Target sampling interval, in seconds.
    sample_interval_s: float = 0.05
    #: Fractional throughput loss that counts as a regression.
    throttle_threshold: float = 0.05
    #: Optional callable returning degrees Celsius from the device under test.
    thermometer: Callable[[], float] | None = None
    #: Anything else worth pinning: firmware, ambient temperature, cooling.
    conditions: dict[str, Any] = field(default_factory=dict)

    @property
    def load_s(self) -> float:
        return self.windows * self.window_s

    def as_dict(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "idle_s": self.idle_s,
            "windows": self.windows,
            "window_s": self.window_s,
            "sample_interval_s": self.sample_interval_s,
            "throttle_threshold": self.throttle_threshold,
            "has_thermometer": self.thermometer is not None,
            "conditions": dict(self.conditions),
        }


class Sampler(Protocol):
    """How readings are taken while the workload runs."""

    def kind(self) -> str: ...
    def start(self, instrument: Instrument, clock: Clock, t0: float) -> None: ...
    def poll(self) -> None:
        """Called by the session between units of work; may be a no-op."""

    def stop(self) -> list[Sample]: ...


class InlineSampler:
    """Reads between units of work. Exactly reproducible, and undersamples.

    Between invocations means *not during* one. On a device whose inference takes
    longer than the sample interval, the peak draw of the inference itself is
    invisible to this sampler, and the energy integral interpolates across it.
    That is a real limitation, recorded in the report as ``sampler: inline``, and
    the reason :class:`ThreadedSampler` exists.
    """

    def __init__(self) -> None:
        self._samples: list[Sample] = []
        self._instrument: Instrument | None = None
        self._clock: Clock | None = None
        self._t0 = 0.0

    def kind(self) -> str:
        return "inline"

    def start(self, instrument: Instrument, clock: Clock, t0: float) -> None:
        self._instrument, self._clock, self._t0 = instrument, clock, t0
        self._samples = []
        self.poll()

    def poll(self) -> None:
        if self._instrument is None or self._clock is None:
            return
        self._samples.append(
            self._instrument.read(self._clock.monotonic() - self._t0)
        )

    def stop(self) -> list[Sample]:
        self.poll()
        return list(self._samples)


class ThreadedSampler:
    """Reads on a background thread at a target rate, including mid-inference.

    Uses the wall clock: a background thread and a simulated clock do not
    combine, so this sampler is for real runs and :class:`InlineSampler` is for
    the test suite. The report says which was used, because the two do not
    produce comparable peak figures.
    """

    def __init__(self, interval_s: float) -> None:
        self.interval_s = interval_s
        self._samples: list[Sample] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def kind(self) -> str:
        return "threaded"

    def start(self, instrument: Instrument, clock: Clock, t0: float) -> None:
        self._samples = []
        self._stop.clear()

        def loop() -> None:
            while not self._stop.is_set():
                s = instrument.read(clock.monotonic() - t0)
                with self._lock:
                    self._samples.append(s)
                self._stop.wait(self.interval_s)

        self._thread = threading.Thread(target=loop, name="mh-sampler", daemon=True)
        self._thread.start()

    def poll(self) -> None:
        return None

    def stop(self) -> list[Sample]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        with self._lock:
            return list(self._samples)


@dataclass(frozen=True, slots=True)
class RunResult:
    """The raw outcome of a run, before it is shaped into a report."""

    spec: SessionSpec
    idle: EnergyResult
    load: EnergyResult
    latency: LatencySummary
    windows: list[Window]
    throttle: ThrottleVerdict
    operations: int
    joules_per_operation: float
    joules_per_operation_above_idle: float
    sampler_kind: str


class Session:
    """Drives one instrument, one workload, one run."""

    def __init__(
        self,
        instrument: Instrument,
        workload: Any,
        spec: SessionSpec,
        clock: Clock | None = None,
        sampler: Sampler | None = None,
    ) -> None:
        self.instrument = instrument
        self.workload = workload
        self.spec = spec
        self.clock = clock or SystemClock()
        self.sampler = sampler or InlineSampler()

    # ------------------------------------------------------------------ helpers
    def _set_duty(self, duty: float) -> None:
        setter = getattr(self.instrument, "set_duty", None)
        if callable(setter):
            setter(duty)

    def _temperature(self) -> float | None:
        return self.spec.thermometer() if self.spec.thermometer else None

    # ---------------------------------------------------------------------- run
    def run(self) -> RunResult:
        spec = self.spec
        self.instrument.open()
        try:
            t0 = self.clock.monotonic()

            # -- idle baseline -------------------------------------------------
            self._set_duty(0.0)
            idle_sampler = InlineSampler()
            idle_sampler.start(self.instrument, self.clock, t0)
            while self.clock.monotonic() - t0 < spec.idle_s:
                self.clock.sleep(spec.sample_interval_s)
                idle_sampler.poll()
            idle_samples = idle_sampler.stop()
            idle = integrate_energy(idle_samples, self.instrument.identity())

            # -- sustained load ------------------------------------------------
            self.workload.prepare()
            load_t0 = self.clock.monotonic()
            self.sampler.start(self.instrument, self.clock, load_t0)

            latencies: list[float] = []
            windows: list[Window] = []
            operations = 0

            for w in range(spec.windows):
                w_start = w * spec.window_s
                w_end = w_start + spec.window_s
                w_ops = 0
                w_latencies: list[float] = []
                w_temp: float | None = None

                while self.clock.monotonic() - load_t0 < w_end:
                    self._set_duty(1.0)
                    started = self.clock.monotonic()
                    self.workload.invoke()
                    elapsed = self.clock.monotonic() - started
                    self._set_duty(0.0)
                    latencies.append(elapsed)
                    w_latencies.append(elapsed)
                    w_ops += 1
                    operations += 1
                    self.sampler.poll()
                    t = self._temperature()
                    if t is not None:
                        w_temp = t if w_temp is None else max(w_temp, t)
                    if elapsed <= 0:  # pragma: no cover - guards a pathological clock
                        break

                windows.append(
                    Window(
                        index=w,
                        start_s=w_start,
                        end_s=w_end,
                        operations=w_ops,
                        mean_watts=0.0,  # filled in below, once samples exist
                        mean_latency_s=(
                            sum(w_latencies) / len(w_latencies) if w_latencies else 0.0
                        ),
                        max_temperature_c=w_temp,
                    )
                )

            load_samples = self.sampler.stop()
            self.workload.teardown()
            load = integrate_energy(load_samples, self.instrument.identity())
            windows = _attach_window_power(windows, load_samples)

            throttle = assess_throttling(windows, spec.throttle_threshold)
            latency = LatencySummary.from_latencies(latencies)

            per_op = load.joules / operations if operations else 0.0
            marginal, _ = energy_above_idle(load, idle.mean_watts)
            per_op_above_idle = marginal / operations if operations else 0.0

            return RunResult(
                spec=spec,
                idle=idle,
                load=load,
                latency=latency,
                windows=windows,
                throttle=throttle,
                operations=operations,
                joules_per_operation=per_op,
                joules_per_operation_above_idle=per_op_above_idle,
                sampler_kind=self.sampler.kind(),
            )
        finally:
            self.instrument.close()


def _attach_window_power(windows: list[Window], samples: list[Sample]) -> list[Window]:
    """Fold mean power back into each window from the run-relative sample times."""
    out: list[Window] = []
    for w in windows:
        inside = [s.watts for s in samples if w.start_s <= s.t_s < w.end_s]
        mean_w = sum(inside) / len(inside) if inside else 0.0
        out.append(
            Window(
                index=w.index,
                start_s=w.start_s,
                end_s=w.end_s,
                operations=w.operations,
                mean_watts=mean_w,
                mean_latency_s=w.mean_latency_s,
                max_temperature_c=w.max_temperature_c,
            )
        )
    return out
