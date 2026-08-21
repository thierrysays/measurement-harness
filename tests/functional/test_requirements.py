"""Functional: one test per requirement in `docs/FUNCTIONAL_SPEC.md`.

These are written from the specification, not from the code. Each one is named
for the requirement it discharges, so a reader who will never open
`src/` can tell whether a claim made about this harness is true. Where a
requirement is about an artefact leaving the machine, the test runs the CLI as a
real subprocess — a tool that only works when imported by its own test suite is
a tool nobody can run.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from measurement_harness.clock import ManualClock
from measurement_harness.energy_model import export_energy_model
from measurement_harness.errors import NotPortedError, SyntheticResultRefused
from measurement_harness.instruments.ina219 import INA219Instrument
from measurement_harness.instruments.synthetic import (
    SyntheticInstrument,
    SyntheticProfile,
)
from measurement_harness.report import Report
from measurement_harness.session import InlineSampler, Session, SessionSpec
from measurement_harness.workload import SyntheticWorkload


def _run(tmp_path, cli_env, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "measurement_harness.cli", *args],
        capture_output=True, text=True, cwd=tmp_path, env=cli_env,
    )


# ------------------------------------------------------------------ FR-1
def test_fr1_a_run_records_the_conditions_it_was_taken_under(tmp_path, cli_env):
    """FR-1 — a report states its instrument, its session and its provenance."""
    out = tmp_path / "r.json"
    assert _run(tmp_path, cli_env, "run", "--device", "board-x", "--windows", "3",
                "--window-s", "5", "--idle-s", "2", "--ambient", "21.5",
                "--out", str(out)).returncode == 0
    body = json.loads(out.read_text())
    assert body["session"]["device"] == "board-x"
    assert body["session"]["conditions"]["ambient_c"] == 21.5
    assert body["instrument"]["kind"]
    assert body["provenance"]["kind"] in ("measured", "synthetic")
    assert body["provenance"]["sampler"] in ("inline", "threaded")
    assert body["provenance"]["harness_version"]


# ------------------------------------------------------------------ FR-2
def test_fr2_the_quoted_figure_excludes_the_idle_floor(tmp_path, cli_env):
    """FR-2 — energy per operation is quoted above idle, and idle is measured."""
    out = tmp_path / "r.json"
    _run(tmp_path, cli_env, "run", "--device", "b", "--windows", "3",
         "--window-s", "5", "--idle-s", "3", "--out", str(out))
    body = json.loads(out.read_text())
    assert body["idle"]["sample_count"] > 1
    assert body["idle"]["mean_watts"] > 0
    assert 0 < body["joules_per_operation_above_idle"] < body["joules_per_operation"]


# ------------------------------------------------------------------ FR-3
def test_fr3_a_sustained_run_is_windowed_and_assessed(tmp_path, cli_env):
    """FR-3 — the load phase is sliced into windows and a verdict is reached."""
    out = tmp_path / "r.json"
    _run(tmp_path, cli_env, "run", "--device", "b", "--windows", "5",
         "--window-s", "30", "--idle-s", "2", "--slowdown", "25", "--out", str(out))
    body = json.loads(out.read_text())
    assert len(body["windows"]) == 5
    assert body["thermal"]["throttled"] is True
    assert body["thermal"]["onset_s"] is not None
    assert body["windows"][-1]["throughput_ops_s"] < body["windows"][0]["throughput_ops_s"]


def test_fr3_a_run_that_holds_its_throughput_is_not_flagged(tmp_path, cli_env):
    out = tmp_path / "r.json"
    _run(tmp_path, cli_env, "run", "--device", "b", "--windows", "5",
         "--window-s", "30", "--idle-s", "2", "--out", str(out))
    assert json.loads(out.read_text())["thermal"]["throttled"] is False


# ------------------------------------------------------------------ FR-4
def test_fr4_a_report_can_be_verified_by_someone_who_did_not_produce_it(tmp_path, cli_env):
    """FR-4 — verification is a separate command, sharing no state with the run."""
    out = tmp_path / "r.json"
    _run(tmp_path, cli_env, "run", "--device", "b", "--windows", "2",
         "--window-s", "5", "--idle-s", "1", "--out", str(out))
    check = _run(tmp_path, cli_env, "verify", str(out))
    assert check.returncode == 0
    assert "verified" in check.stdout


def test_fr4_verification_fails_loudly_on_an_altered_report(tmp_path, cli_env):
    out = tmp_path / "r.json"
    _run(tmp_path, cli_env, "run", "--device", "b", "--windows", "2",
         "--window-s", "5", "--idle-s", "1", "--out", str(out))
    body = json.loads(out.read_text())
    body["joules_per_operation_above_idle"] *= 0.5
    out.write_text(json.dumps(body))
    check = _run(tmp_path, cli_env, "verify", str(out))
    assert check.returncode == 2
    assert "report-invalid" in check.stderr


# ------------------------------------------------------------------ FR-5
def test_fr5_a_synthetic_run_cannot_be_exported_as_a_measurement(tmp_path, cli_env):
    """FR-5 — the export refuses a rehearsal unless asked in as many words."""
    out = tmp_path / "r.json"
    _run(tmp_path, cli_env, "run", "--device", "b", "--windows", "2",
         "--window-s", "5", "--idle-s", "1", "--out", str(out))
    refused = _run(tmp_path, cli_env, "energy-model", str(out))
    assert refused.returncode == 2
    assert "synthetic-result-refused" in refused.stderr

    allowed = _run(tmp_path, cli_env, "energy-model", str(out), "--allow-synthetic")
    assert allowed.returncode == 0
    assert "not measured" in json.loads(allowed.stdout)["source"]


# ------------------------------------------------------------------ FR-6
def test_fr6_an_instrument_that_has_never_run_refuses_to_produce_readings(tmp_path, cli_env):
    """FR-6 — an unported driver raises rather than returning plausible numbers."""
    with pytest.raises(NotPortedError):
        INA219Instrument().open()
    result = _run(tmp_path, cli_env, "run", "--device", "b", "--instrument", "ina219",
                  "--windows", "1", "--window-s", "1", "--idle-s", "1",
                  "--out", str(tmp_path / "r.json"))
    assert result.returncode == 2
    assert "instrument-not-ported" in result.stderr
    assert not (tmp_path / "r.json").exists()


# ------------------------------------------------------------------ FR-7
def test_fr7_the_same_inputs_produce_the_same_figures():
    """FR-7 — a run is reproducible from its seed, or the format is untestable."""
    def once() -> tuple[float, int, float]:
        clock = ManualClock()
        instrument = SyntheticInstrument(SyntheticProfile(), seed=11, clock=clock)
        workload = SyntheticWorkload(latency_s=0.02, clock=clock)
        spec = SessionSpec(device="d", idle_s=2.0, windows=3, window_s=10.0)
        result = Session(instrument, workload, spec, clock=clock,
                         sampler=InlineSampler()).run()
        return result.load.joules, result.operations, result.latency.p95_s

    assert once() == once()


def test_fr7_two_identical_runs_digest_identically():
    from tests.conftest import build_report

    a = build_report("measured")
    b = build_report("measured")
    assert a.report_id == b.report_id


# ------------------------------------------------------------------ FR-8
def test_fr8_a_report_carries_an_error_bar_or_says_it_has_none(tmp_path, cli_env):
    """FR-8 — every energy figure leaves with an uncertainty attached."""
    out = tmp_path / "r.json"
    _run(tmp_path, cli_env, "run", "--device", "b", "--windows", "2",
         "--window-s", "5", "--idle-s", "1", "--out", str(out))
    body = json.loads(out.read_text())
    assert "joules_uncertainty" in body["load"]
    assert "joules_uncertainty" in body["idle"]
    # The synthetic instrument declares no accuracy, so the bar is zero — and
    # the instrument block is present so a reader can see why.
    assert body["load"]["joules_uncertainty"] == 0.0
    assert body["instrument"]["accuracy_pct"] == 0.0


# ------------------------------------------------------------------ FR-9
def test_fr9_the_export_carries_the_sentence_not_just_the_number(measured_report):
    """FR-9 — a consumer that keeps the value can also keep its qualification."""
    export = export_energy_model(measured_report, actions={"inference": 1.0})
    payload = export.as_dict()
    assert payload["values"]["inference"] > 0
    assert measured_report.report_id in payload["source"]
    assert payload["basis"] == "above_idle"
    assert payload["uncertainty_j_per_operation"] > 0


def test_fr9_a_scaled_action_is_never_described_as_measured(measured_report):
    export = export_energy_model(
        measured_report, actions={"inference": 1.0, "batch8": 8.0}
    )
    assert "scaled (not measured) for: batch8" in export.source


# ------------------------------------------------------------------ FR-10
def test_fr10_a_report_round_trips_through_a_file_unchanged(tmp_path, measured_report):
    """FR-10 — writing and reading a report does not change what it says."""
    path = measured_report.write(tmp_path / "r.json")
    reloaded = Report.read(path)
    reloaded.verify()
    assert reloaded.body == measured_report.body
    assert reloaded.report_id == measured_report.report_id


def test_fr10_the_synthetic_export_path_still_refuses_by_default(synthetic_report):
    with pytest.raises(SyntheticResultRefused):
        export_energy_model(synthetic_report)
