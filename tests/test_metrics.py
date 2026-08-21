"""Energy integration and latency percentiles, including where they refuse."""

import pytest

from measurement_harness.errors import InsufficientSamples
from measurement_harness.instruments.base import InstrumentIdentity, Sample
from measurement_harness.metrics import (
    LatencySummary,
    energy_above_idle,
    integrate_energy,
)


def _flat(watts: float, n: int, dt: float, volts: float = 5.0):
    return [Sample(t_s=i * dt, volts=volts, amps=watts / volts) for i in range(n)]


def test_constant_power_integrates_to_power_times_time():
    samples = _flat(2.0, 11, 0.1)  # 2 W for exactly 1.0 s
    result = integrate_energy(samples)
    assert result.joules == pytest.approx(2.0, rel=1e-9)
    assert result.duration_s == pytest.approx(1.0, rel=1e-9)
    assert result.mean_watts == pytest.approx(2.0, rel=1e-9)


def test_a_ramp_integrates_to_the_trapezoid_not_the_endpoint():
    # 0 W to 4 W over one second: 2 J, not 4 J and not 0 J.
    samples = [Sample(t_s=0.0, volts=5.0, amps=0.0), Sample(t_s=1.0, volts=5.0, amps=0.8)]
    assert integrate_energy(samples).joules == pytest.approx(2.0)


def test_uneven_sample_spacing_is_respected():
    # A stalled sampler must not be treated as evenly spaced.
    samples = [
        Sample(t_s=0.0, volts=5.0, amps=0.2),
        Sample(t_s=0.1, volts=5.0, amps=0.2),
        Sample(t_s=2.1, volts=5.0, amps=0.2),  # a two-second gap
    ]
    result = integrate_energy(samples)
    assert result.joules == pytest.approx(1.0 * 2.1, rel=1e-9)
    assert result.max_gap_s == pytest.approx(2.0)


def test_a_single_sample_is_refused_rather_than_extrapolated():
    with pytest.raises(InsufficientSamples):
        integrate_energy(_flat(2.0, 1, 0.1))


def test_timestamps_going_backwards_are_refused():
    samples = [
        Sample(t_s=0.0, volts=5.0, amps=0.2),
        Sample(t_s=-0.5, volts=5.0, amps=0.2),
    ]
    with pytest.raises(ValueError):
        integrate_energy(samples)


def test_uncertainty_carries_both_the_rated_accuracy_and_the_resolution_floor():
    identity = InstrumentIdentity(
        kind="test", description="", accuracy_pct=1.0, resolution_a=0.001
    )
    result = integrate_energy(_flat(2.0, 11, 0.1), identity)
    # 1% of 2 J, plus 1 mA * 5 V * 1 s.
    assert result.joules_uncertainty == pytest.approx(0.02 + 0.005, rel=1e-6)


def test_an_instrument_with_no_declared_accuracy_gets_no_error_bar():
    # Zero is honest here: it says the instrument declared nothing, and the
    # report carries the instrument block so a reader can see that it did not.
    assert integrate_energy(_flat(2.0, 11, 0.1)).joules_uncertainty == 0.0


def test_energy_above_idle_removes_the_floor_and_never_goes_negative():
    result = integrate_energy(_flat(2.0, 11, 0.1))
    marginal, _ = energy_above_idle(result, idle_watts=0.5)
    assert marginal == pytest.approx(1.5)
    quieter, _ = energy_above_idle(result, idle_watts=99.0)
    assert quieter == 0.0


def test_percentiles_are_values_that_actually_occurred():
    summary = LatencySummary.from_latencies([0.01, 0.02, 0.03, 0.04, 1.0])
    assert summary.p50_s == 0.03
    assert summary.p99_s == 1.0
    assert summary.max_s == 1.0


def test_one_latency_is_not_a_summary():
    with pytest.raises(InsufficientSamples):
        LatencySummary.from_latencies([0.02])
