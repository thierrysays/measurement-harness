"""Exporting a figure downstream, and refusing to launder a rehearsal as one."""

import pytest

from measurement_harness.energy_model import (
    BASIS_ABOVE_IDLE,
    BASIS_TOTAL,
    export_energy_model,
)
from measurement_harness.errors import SyntheticResultRefused


def test_a_synthetic_run_cannot_be_exported_as_a_measurement(synthetic_report):
    with pytest.raises(SyntheticResultRefused) as excinfo:
        export_energy_model(synthetic_report)
    assert excinfo.value.code == "synthetic-result-refused"


def test_a_synthetic_run_may_be_exported_but_carries_the_label(synthetic_report):
    export = export_energy_model(synthetic_report, allow_synthetic=True)
    assert "synthetic" in export.source
    assert "not measured" in export.source


def test_a_measured_run_exports_with_the_instrument_and_the_report_id(measured_report):
    export = export_energy_model(measured_report)
    assert export.source.startswith("measured — ")
    assert measured_report.report_id in export.source
    assert "not measured" not in export.source


def test_the_default_basis_is_energy_above_idle(measured_report):
    above = export_energy_model(measured_report, basis=BASIS_ABOVE_IDLE)
    total = export_energy_model(measured_report, basis=BASIS_TOTAL)
    assert export_energy_model(measured_report).values == above.values
    assert above.values["inference"] < total.values["inference"]


def test_scaled_actions_are_named_as_scaled_rather_than_measured(measured_report):
    export = export_energy_model(
        measured_report, actions={"inference": 1.0, "inference_batch4": 4.0}
    )
    assert export.values["inference_batch4"] == pytest.approx(
        export.values["inference"] * 4
    )
    assert "scaled (not measured) for: inference_batch4" in export.source


def test_the_export_carries_a_per_operation_error_bar(measured_report):
    assert export_energy_model(measured_report).uncertainty_j_per_operation > 0


def test_a_throttled_run_says_so_in_the_source_string(report_factory):
    report = report_factory("measured", slowdown=30.0, windows=5, window_s=30.0)
    assert report.body["thermal"]["throttled"] is True
    export = export_energy_model(report)
    assert "throughput regressed" in export.source


def test_an_unknown_basis_is_refused(measured_report):
    with pytest.raises(ValueError):
        export_energy_model(measured_report, basis="whatever")
