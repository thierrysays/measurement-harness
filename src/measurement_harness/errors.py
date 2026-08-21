"""One exception per failure mode, each with a stable ``code``.

Codes are part of the interface. A wrapper script that greps stderr is a
wrapper script that breaks; a wrapper script that switches on ``code`` is not.
"""

from __future__ import annotations


class MeasurementError(Exception):
    """Base class. Carries a stable, machine-readable ``code``."""

    code = "measurement-error"


class InstrumentNotPresent(MeasurementError):
    """The instrument could not be opened, so nothing was measured.

    Raised rather than returning zeroes. A run that produced no samples must not
    be indistinguishable from a run that measured a device drawing no current.
    """

    code = "instrument-not-present"

    def __init__(self, instrument: str, detail: str) -> None:
        super().__init__(f"{instrument}: {detail}")
        self.instrument = instrument
        self.detail = detail


class NotPortedError(MeasurementError):
    """A driver exists as a declaration but has not been run against hardware."""

    code = "instrument-not-ported"

    def __init__(self, instrument: str, porting_note: str) -> None:
        super().__init__(f"{instrument} is not ported: {porting_note}")
        self.instrument = instrument
        self.porting_note = porting_note


class InsufficientSamples(MeasurementError):
    """Fewer samples than the analysis needs, so no figure is produced."""

    code = "insufficient-samples"

    def __init__(self, have: int, need: int, what: str) -> None:
        super().__init__(f"{what} needs at least {need} samples, have {have}")
        self.have = have
        self.need = need


class SyntheticResultRefused(MeasurementError):
    """A synthetic run was asked to stand in for a measured figure.

    The harness will happily produce synthetic reports — they are how the
    pipeline is tested without hardware. It will not let one leave the building
    labelled as a measurement.
    """

    code = "synthetic-result-refused"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
