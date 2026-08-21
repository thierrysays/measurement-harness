"""The artefact: what it carries, and how a reader catches it being edited."""

import json

import pytest

from measurement_harness.report import SCHEMA, Report, ReportInvalid


def test_a_report_verifies_against_its_own_digest(measured_report, tmp_path):
    path = measured_report.write(tmp_path / "report.json")
    Report.read(path).verify()


def test_an_edited_report_fails_verification_and_says_so(measured_report, tmp_path):
    path = measured_report.write(tmp_path / "report.json")
    raw = json.loads(path.read_text())
    raw["joules_per_operation_above_idle"] *= 0.5  # a flattering edit
    path.write_text(json.dumps(raw))
    with pytest.raises(ReportInvalid) as excinfo:
        Report.read(path).verify()
    assert "digest mismatch" in str(excinfo.value)


def test_editing_the_instrument_block_is_caught_too(measured_report, tmp_path):
    # The most tempting edit: the same numbers, attributed to a better meter.
    path = measured_report.write(tmp_path / "report.json")
    raw = json.loads(path.read_text())
    raw["instrument"]["accuracy_pct"] = 0.01
    path.write_text(json.dumps(raw))
    with pytest.raises(ReportInvalid):
        Report.read(path).verify()


def test_a_report_without_an_identifier_is_refused(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"schema": SCHEMA}))
    with pytest.raises(ReportInvalid):
        Report.read(path)


def test_an_unknown_schema_is_refused_before_the_digest_is_trusted(measured_report, tmp_path):
    body = dict(measured_report.body)
    body["schema"] = "measurement-harness/report/v2"
    forged = Report(body=body, report_id=__import__(
        "measurement_harness.canonical", fromlist=["digest"]).digest(body))
    with pytest.raises(ReportInvalid):
        forged.verify()


def test_the_report_carries_provenance_where_nobody_can_miss_it(synthetic_report):
    assert synthetic_report.body["provenance"]["kind"] == "synthetic"
    assert synthetic_report.is_measured is False


def test_the_report_carries_the_sampler_because_peaks_are_not_comparable(measured_report):
    assert measured_report.body["provenance"]["sampler"] == "inline"


def test_the_report_carries_an_error_bar_on_the_energy_figure(measured_report):
    assert measured_report.body["load"]["joules_uncertainty"] > 0
