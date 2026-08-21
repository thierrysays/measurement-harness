"""What the harness requires of an instrument, and nothing more.

The core of this package never learns what it is talking to. It opens something,
reads volts and amps from it, and closes it. That is the whole contract, and it
is small on purpose: an INA219 shunt monitor over I2C, a programmable bench
supply over SCPI, a USB-C inline analyser, a smart plug on the mains side of a
DC brick, and a synthetic generator all satisfy it identically.

The identity block is not decoration. A power figure without the instrument that
produced it, its rated accuracy and its shunt configuration is a number, not a
measurement — nobody downstream can say how much of the difference between two
runs is the device and how much is the meter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Sample:
    """One reading: seconds since the run started, volts, amps.

    Power is derived rather than stored. Instruments that report power directly
    still give volts and amps, because a rail sagging under load is the most
    common explanation for a throughput cliff and it is invisible in watts alone.
    """

    t_s: float
    volts: float
    amps: float

    @property
    def watts(self) -> float:
        return self.volts * self.amps

    def as_dict(self) -> dict[str, float]:
        return {"t_s": self.t_s, "volts": self.volts, "amps": self.amps}


@dataclass(frozen=True, slots=True)
class InstrumentIdentity:
    """Everything a reader needs to judge how much to trust a figure."""

    #: Short stable key, e.g. ``ina219`` or ``synthetic``.
    kind: str
    #: Human description, including how it is wired.
    description: str
    #: ``measured`` for a real instrument on a real rail, ``synthetic`` otherwise.
    provenance: str = "measured"
    #: Manufacturer-rated accuracy, as a percentage of reading.
    accuracy_pct: float = 0.0
    #: Smallest current step the instrument can resolve, in amps.
    resolution_a: float = 0.0
    #: Nominal samples per second the driver can sustain.
    sample_rate_hz: float = 0.0
    #: Anything driver-specific worth carrying: shunt value, gain, port, serial.
    settings: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "description": self.description,
            "provenance": self.provenance,
            "accuracy_pct": self.accuracy_pct,
            "resolution_a": self.resolution_a,
            "sample_rate_hz": self.sample_rate_hz,
            "settings": dict(self.settings),
        }


@runtime_checkable
class Instrument(Protocol):
    """Open, read, close. Implement these three and the harness can drive you."""

    def identity(self) -> InstrumentIdentity:
        """Describe the instrument. Called once, recorded in the report."""

    def open(self) -> None:
        """Acquire the device. Raise :class:`~..errors.InstrumentNotPresent` if absent."""

    def read(self, t_s: float) -> Sample:
        """Return one reading, stamped with the caller's run-relative time."""

    def close(self) -> None:
        """Release the device. Must be safe to call twice."""


class UnportedInstrument:
    """A driver that exists as a declaration and refuses to fabricate readings.

    The pattern matters more than the class: a driver written from a datasheet
    but never run against the part is a hypothesis. It belongs in the tree, named
    and documented, raising :class:`~..errors.NotPortedError` — not returning
    plausible numbers that will be believed.
    """

    identity_: InstrumentIdentity
    porting_note: str

    def identity(self) -> InstrumentIdentity:
        return self.identity_

    def open(self) -> None:
        from ..errors import NotPortedError

        raise NotPortedError(self.identity_.kind, self.porting_note)

    def read(self, t_s: float) -> Sample:
        from ..errors import NotPortedError

        raise NotPortedError(self.identity_.kind, self.porting_note)

    def close(self) -> None:
        return None
