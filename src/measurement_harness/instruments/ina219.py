"""INA219 high-side shunt monitor — declared, not yet run against the part.

The INA219 is the obvious first instrument for a Qwiic-equipped bench: a 0.1 Ω
shunt, an I2C address, 12-bit conversion, and a bus-voltage channel that catches
the rail sagging. What follows is written from the datasheet and has driven
nothing. It therefore refuses to produce readings.

Porting note, kept here rather than in an issue tracker because the next person
to open this file is the person who will do it:

* Wire the shunt **high-side**, between supply and device. Low-side wiring puts
  the device ground above the instrument ground and quietly biases every reading.
* A 0.1 Ω shunt at ±320 mV full scale reaches 3.2 A, which covers all five of the
  target boards under load with room for inrush.
* Set the calibration register for the current LSB you actually want, and record
  it in ``settings``: an INA219 report without its calibration value cannot be
  re-derived.
* Continuous conversion at 12-bit averaged over 128 samples gives roughly 8.5 ms
  per reading, i.e. about 117 Hz. That is fast enough for energy integration and
  far too slow for inrush; say so in the report rather than implying otherwise.
* Sample on a monotonic schedule and record the actual timestamp, not the one you
  intended. Integration over assumed-uniform intervals is where energy figures
  quietly acquire a few percent of error.
"""

from __future__ import annotations

from .base import InstrumentIdentity, UnportedInstrument


class INA219Instrument(UnportedInstrument):
    """Declares the instrument, refuses to invent its readings."""

    identity_ = InstrumentIdentity(
        kind="ina219",
        description=(
            "Texas Instruments INA219 high-side current/bus-voltage monitor over "
            "I2C, 0.1 ohm shunt, 12-bit, 128-sample averaging."
        ),
        provenance="measured",
        accuracy_pct=0.5,
        resolution_a=0.0001,
        sample_rate_hz=117.0,
        settings={"shunt_ohms": 0.1, "i2c_address": "0x40", "gain": "1/8 (320mV)"},
    )

    porting_note = (
        "wire the shunt high-side, write the calibration register for the chosen "
        "current LSB and record it in settings, sample on a monotonic schedule and "
        "stamp each reading with the time it was actually taken"
    )
