"""The throttle detector, and the noise it is required to ignore."""

import pytest

from measurement_harness.thermal import Window, assess_throttling


def _window(index: int, ops: int, window_s: float = 60.0, temp=None) -> Window:
    return Window(
        index=index,
        start_s=index * window_s,
        end_s=(index + 1) * window_s,
        operations=ops,
        mean_watts=2.0,
        mean_latency_s=window_s / ops,
        max_temperature_c=temp,
    )


def test_steady_throughput_is_not_a_throttle():
    verdict = assess_throttling([_window(i, 3000) for i in range(5)])
    assert verdict.throttled is False
    assert verdict.onset_s is None


def test_a_sustained_decline_is_a_throttle_and_names_its_onset():
    windows = [_window(0, 3000), _window(1, 3000), _window(2, 2400), _window(3, 2300)]
    verdict = assess_throttling(windows, threshold=0.05)
    assert verdict.throttled is True
    assert verdict.onset_s == 120.0
    assert verdict.regression > 0.05


def test_one_slow_window_is_noise_not_a_throttle():
    # A single stalled window with recovery either side. Without the
    # consecutive-window rule this is where the detector starts crying wolf.
    windows = [_window(0, 3000), _window(1, 3000), _window(2, 1500), _window(3, 3000),
               _window(4, 3000), _window(5, 3000), _window(6, 3000), _window(7, 3000)]
    verdict = assess_throttling(windows, threshold=0.05, consecutive=2)
    assert verdict.onset_s is None
    assert verdict.throttled is False


def test_temperature_rise_is_reported_only_when_the_device_supplied_one():
    without = assess_throttling([_window(0, 3000), _window(1, 2000)])
    assert without.temperature_rise_c is None

    with_temps = assess_throttling(
        [_window(0, 3000, temp=41.0), _window(1, 2000, temp=78.5)]
    )
    assert with_temps.temperature_rise_c == pytest.approx(37.5)


def test_the_verdict_refuses_to_claim_a_cause():
    verdict = assess_throttling([_window(0, 3000), _window(1, 2000), _window(2, 1900)])
    assert "not attributed" in verdict.caveat


def test_a_single_window_cannot_be_assessed():
    with pytest.raises(ValueError):
        assess_throttling([_window(0, 3000)])
