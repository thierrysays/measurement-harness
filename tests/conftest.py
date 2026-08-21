import pytest

from measurement_harness.clock import ManualClock
from measurement_harness.instruments.base import InstrumentIdentity
from measurement_harness.instruments.synthetic import SyntheticInstrument, SyntheticProfile
from measurement_harness.report import Report
from measurement_harness.session import InlineSampler, Session, SessionSpec
from measurement_harness.workload import SyntheticWorkload


class DeclaredInstrument(SyntheticInstrument):
    """A synthetic source wearing a declared identity.

    The interesting downstream tests are about what happens to a report that
    claims to be measured, including one that has no business claiming it. This
    is the only place in the tree where that claim can be manufactured, and it
    is a test fixture on purpose.
    """

    def __init__(self, provenance: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._provenance = provenance

    def identity(self) -> InstrumentIdentity:
        base = super().identity()
        return InstrumentIdentity(
            kind="ina219" if self._provenance == "measured" else base.kind,
            description=base.description,
            provenance=self._provenance,
            accuracy_pct=0.5,
            resolution_a=0.0001,
            sample_rate_hz=117.0,
            settings=base.settings,
        )


def build_report(
    provenance: str = "synthetic",
    slowdown: float = 0.0,
    windows: int = 3,
    window_s: float = 10.0,
) -> Report:
    """A small but complete run, shaped into a report."""
    clock = ManualClock()
    instrument = DeclaredInstrument(
        provenance,
        profile=SyntheticProfile(idle_a=0.12, active_a=0.5),
        seed=3,
        clock=clock,
    )
    workload = SyntheticWorkload(
        latency_s=0.02, thermal_slowdown_pct_per_min=slowdown, clock=clock
    )
    spec = SessionSpec(device="dut-1", idle_s=2.0, windows=windows, window_s=window_s)
    result = Session(instrument, workload, spec, clock=clock, sampler=InlineSampler()).run()

    return Report.from_run(
        result,
        instrument_identity=instrument.identity().as_dict(),
        workload=workload.describe(),
        produced_at="2026-08-21T09:00:00+00:00",
        harness_version="0.1.0",
    )


@pytest.fixture
def synthetic_report() -> Report:
    return build_report("synthetic")


@pytest.fixture
def measured_report() -> Report:
    return build_report("measured")
