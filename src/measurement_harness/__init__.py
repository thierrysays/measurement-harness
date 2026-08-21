"""measurement-harness — power, latency and thermal behaviour under sustained load.

This package measures a device under test. It does not govern one, does not
decide whether a workload should run, and holds no opinion about what the
numbers mean. That separation is deliberate: a measurement instrument that also
enforces policy is an instrument nobody trusts, because its readings and its
verdicts share a failure mode.

Two properties are load-bearing:

* **Instrument-agnostic.** The core knows only :class:`~.instruments.base.Instrument`
  — something that can be opened, sampled for volts and amps, and closed. A
  shunt monitor over I2C, a bench supply over SCPI, a USB-C power analyser and a
  synthetic generator are all the same shape.
* **Provenance is carried, never inferred.** Every report states which
  instrument produced it and whether the run was ``measured`` or ``synthetic``.
  A synthetic run is a rehearsal of the pipeline, and the artefact says so in a
  field a consumer must read.
"""

from .metrics import EnergyResult, LatencySummary
from .report import Report, ReportProvenance
from .session import Session, SessionSpec
from .thermal import ThrottleVerdict

__all__ = [
    "Report",
    "ReportProvenance",
    "Session",
    "SessionSpec",
    "EnergyResult",
    "LatencySummary",
    "ThrottleVerdict",
]

__version__ = "0.1.0"
