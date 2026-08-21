import os
import pathlib

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
def report_factory():
    """Build a report to order: provenance, slowdown, window count."""
    return build_report


@pytest.fixture
def synthetic_report() -> Report:
    return build_report("synthetic")


@pytest.fixture
def measured_report() -> Report:
    return build_report("measured")


@pytest.fixture
def cli_env() -> dict[str, str]:
    """Environment for a subprocess that must find the package.

    The end-to-end tiers run the CLI as a real process rather than calling
    ``main()``, because a tool that only works when imported by its own test
    suite is a tool nobody can run. This keeps that honest whether the package
    was installed with ``pip install -e .`` or is merely on ``PYTHONPATH``.
    """
    src = str(pathlib.Path(__file__).resolve().parent.parent / "src")
    env = dict(os.environ)
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    return env


# The tier a test belongs to is the directory it sits in. Applying the marker
# from the path rather than by hand means a test cannot be moved into a tier
# and keep the old label, which is the way tier markers usually rot.
_TIERS = {"unit", "functional", "smoke", "security", "pentest"}


def pytest_collection_modifyitems(items) -> None:
    for item in items:
        for part in pathlib.Path(str(item.fspath)).parts:
            if part in _TIERS:
                item.add_marker(getattr(pytest.mark, part))
                break
