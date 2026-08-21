"""A whole run under a manual clock: a six-minute soak, in microseconds."""

import pytest

from measurement_harness.clock import ManualClock
from measurement_harness.instruments.synthetic import (
    SyntheticInstrument,
    SyntheticProfile,
)
from measurement_harness.session import InlineSampler, Session, SessionSpec
from measurement_harness.workload import SyntheticWorkload


def _run(slowdown=0.0, droop=0.0, windows=6, thermometer=None, seed=5):
    clock = ManualClock()
    instrument = SyntheticInstrument(
        SyntheticProfile(idle_a=0.12, active_a=0.50, thermal_droop_pct_per_min=droop),
        seed=seed,
        clock=clock,
    )
    workload = SyntheticWorkload(
        latency_s=0.020, thermal_slowdown_pct_per_min=slowdown, clock=clock
    )
    spec = SessionSpec(
        device="device-under-test",
        idle_s=5.0,
        windows=windows,
        window_s=30.0,
        sample_interval_s=0.05,
        thermometer=thermometer,
    )
    return Session(instrument, workload, spec, clock=clock, sampler=InlineSampler()).run()


def test_a_run_produces_one_window_per_configured_window():
    result = _run()
    assert len(result.windows) == 6
    assert result.operations > 0


def test_the_idle_baseline_is_measured_before_the_load_starts():
    result = _run()
    assert result.idle.mean_watts == pytest.approx(0.12 * 5.0, rel=0.05)
    assert result.load.mean_watts > result.idle.mean_watts


def test_per_operation_energy_excludes_the_idle_floor():
    result = _run()
    assert result.joules_per_operation_above_idle < result.joules_per_operation


def test_a_workload_that_stays_fast_is_not_reported_as_throttled():
    assert _run(slowdown=0.0).throttle.throttled is False


def test_a_workload_that_slows_under_sustained_load_is_caught():
    result = _run(slowdown=20.0)
    assert result.throttle.throttled is True
    assert result.throttle.onset_s is not None
    assert result.throttle.sustained_ops_s < result.throttle.first_window_ops_s


def test_the_run_is_reproducible_from_the_same_seed():
    a, b = _run(seed=11), _run(seed=11)
    assert a.load.joules == b.load.joules
    assert a.operations == b.operations
    assert a.latency.p95_s == b.latency.p95_s


def test_a_temperature_series_is_carried_when_the_device_offers_one():
    readings = iter([40.0 + i * 0.05 for i in range(100000)])
    result = _run(thermometer=lambda: next(readings))
    assert result.throttle.temperature_rise_c is not None
    assert all(w.max_temperature_c is not None for w in result.windows)


def test_the_instrument_is_closed_even_when_the_workload_explodes():
    class ExplodingWorkload(SyntheticWorkload):
        def invoke(self) -> None:
            raise RuntimeError("model failed to load")

    clock = ManualClock()
    instrument = SyntheticInstrument(seed=1, clock=clock)
    workload = ExplodingWorkload(clock=clock)
    spec = SessionSpec(device="x", idle_s=1.0, windows=1, window_s=1.0)
    with pytest.raises(RuntimeError):
        Session(instrument, workload, spec, clock=clock, sampler=InlineSampler()).run()
    assert instrument._open is False
