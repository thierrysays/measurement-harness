"""Instruments, and the readings they decline to invent."""

import pytest

from measurement_harness.clock import ManualClock
from measurement_harness.errors import InstrumentNotPresent, NotPortedError
from measurement_harness.instruments.base import Instrument
from measurement_harness.instruments.ina219 import INA219Instrument
from measurement_harness.instruments.synthetic import (
    SyntheticInstrument,
    SyntheticProfile,
)


def test_the_synthetic_instrument_satisfies_the_protocol():
    assert isinstance(SyntheticInstrument(), Instrument)


def test_reading_before_opening_is_an_error_not_a_zero():
    # A run that never acquired the instrument must not be mistaken for a run
    # that measured a device drawing nothing.
    with pytest.raises(InstrumentNotPresent):
        SyntheticInstrument().read(0.0)


def test_an_unported_driver_refuses_to_open_and_says_what_is_missing():
    with pytest.raises(NotPortedError) as excinfo:
        INA219Instrument().open()
    assert excinfo.value.code == "instrument-not-ported"
    assert "high-side" in excinfo.value.porting_note


def test_an_unported_driver_still_declares_its_identity():
    # The declaration is the point: the report format, the settings that will
    # need recording, and the rated accuracy are all decided before the part
    # arrives, not improvised on the bench.
    identity = INA219Instrument().identity()
    assert identity.kind == "ina219"
    assert identity.accuracy_pct > 0
    assert identity.settings["shunt_ohms"] == 0.1


def test_the_synthetic_instrument_declares_itself_synthetic():
    assert SyntheticInstrument().identity().provenance == "synthetic"


def test_the_same_seed_produces_the_same_readings():
    def run(seed):
        clock = ManualClock()
        inst = SyntheticInstrument(seed=seed, clock=clock)
        inst.open()
        out = []
        for _ in range(20):
            clock.advance(0.05)
            out.append(inst.read(clock.monotonic()).amps)
        return out

    assert run(7) == run(7)
    assert run(7) != run(8)


def test_readings_average_the_interval_rather_than_sampling_the_instant():
    # Half the interval loaded, half idle, read once: the reading is the mean,
    # which is what an averaging shunt monitor reports.
    clock = ManualClock()
    profile = SyntheticProfile(idle_a=0.10, active_a=0.50, noise_a=0.0, ripple_a=0.0)
    inst = SyntheticInstrument(profile, seed=1, clock=clock)
    inst.open()
    inst.set_duty(1.0)
    clock.advance(0.5)
    inst.set_duty(0.0)
    clock.advance(0.5)
    assert inst.read(clock.monotonic()).amps == pytest.approx(0.30, abs=1e-9)


def test_a_loaded_rail_sags_by_the_declared_amount():
    clock = ManualClock()
    profile = SyntheticProfile(volts=5.0, sag_v=0.4, noise_a=0.0, ripple_a=0.0)
    inst = SyntheticInstrument(profile, seed=1, clock=clock)
    inst.open()
    inst.set_duty(1.0)
    clock.advance(1.0)
    assert inst.read(clock.monotonic()).volts == pytest.approx(4.6)
