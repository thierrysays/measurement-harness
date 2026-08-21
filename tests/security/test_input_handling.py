"""Security: what the harness does with input it did not produce.

A measurement report is a file that arrives from somewhere. It may have been
written by an older version, by a different implementation, by a colleague who
edited it in a text editor, or by somebody who wants a particular number to be
believed. None of those are exotic; the last one is the whole reason the digest
exists.

The property under test throughout: **untrusted input can make the harness
refuse, and cannot make it do anything else.** No execution, no traversal, no
unbounded allocation, no silent acceptance.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from measurement_harness import canonical
from measurement_harness.report import SCHEMA, Report, ReportInvalid

SRC = Path(__file__).resolve().parents[2] / "src" / "measurement_harness"


# ------------------------------------------------------------ code execution
def test_the_package_never_evaluates_what_it_reads():
    """No eval, exec, pickle or shell in the package.

    A report is data. The moment a loader can be persuaded to execute part of
    its input, every other control here is decorative.
    """
    forbidden = re.compile(
        r"\b(eval|exec|compile)\s*\(|\bpickle\b|\bmarshal\b|\bshelve\b"
        r"|os\.system|subprocess\.|__import__\s*\("
    )
    offenders = [
        f.name for f in SRC.rglob("*.py") if forbidden.search(f.read_text())
    ]
    assert offenders == []


def test_reports_are_parsed_with_the_json_module_not_a_python_literal():
    # json.loads cannot construct arbitrary objects; ast.literal_eval and
    # yaml.load can be talked into more than their callers expect.
    loader_sources = (SRC / "report.py").read_text()
    assert "json.loads" in loader_sources
    assert "literal_eval" not in loader_sources
    assert "yaml" not in loader_sources


# -------------------------------------------------------------- schema first
def test_an_unknown_schema_is_refused_before_the_digest_is_believed(measured_report):
    body = dict(measured_report.body)
    body["schema"] = "measurement-harness/report/v99"
    forged = Report(body=body, report_id=canonical.digest(body))
    # The digest is internally consistent. It is still refused, because the
    # reader does not know what the fields mean under a schema it has not seen.
    with pytest.raises(ReportInvalid):
        forged.verify()


def test_a_missing_schema_is_refused(measured_report):
    body = {k: v for k, v in measured_report.body.items() if k != "schema"}
    with pytest.raises(ReportInvalid):
        Report(body=body, report_id=canonical.digest(body)).verify()


def test_a_report_without_a_digest_is_refused_rather_than_trusted(tmp_path):
    path = tmp_path / "r.json"
    path.write_text(json.dumps({"schema": SCHEMA, "operations": 1}))
    with pytest.raises(ReportInvalid):
        Report.read(path)


# ------------------------------------------------------------ malformed input
def test_a_truncated_file_fails_to_parse_rather_than_half_loading(tmp_path, measured_report):
    path = measured_report.write(tmp_path / "r.json")
    raw = path.read_text()
    path.write_text(raw[: len(raw) // 2])
    with pytest.raises(json.JSONDecodeError):
        Report.read(path)


def test_a_report_that_is_not_an_object_is_refused(tmp_path):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(["not", "an", "object"]))
    with pytest.raises((ReportInvalid, AttributeError, TypeError)):
        Report.read(path)


def test_deeply_nested_input_raises_rather_than_taking_the_process_down(tmp_path):
    # 100k nested arrays. The requirement is a catchable exception, not a
    # segfault and not a silent success.
    path = tmp_path / "r.json"
    path.write_text("[" * 100_000 + "]" * 100_000)
    with pytest.raises((RecursionError, json.JSONDecodeError, ReportInvalid,
                        AttributeError, TypeError)):
        Report.read(path)


def test_a_non_finite_figure_cannot_be_canonicalised_at_all():
    # NaN survives a JSON round trip in Python and compares unequal to itself.
    # A report carrying one has a digest that depends on the reader.
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            canonical.digest({"joules": bad})


def test_a_non_finite_figure_buried_in_a_window_is_still_caught():
    with pytest.raises(ValueError):
        canonical.digest({"windows": [{"ops": 1}, {"mean_watts": float("nan")}]})


# ---------------------------------------------------------------- filesystem
def test_reading_a_directory_fails_cleanly(tmp_path):
    with pytest.raises((IsADirectoryError, PermissionError, OSError)):
        Report.read(tmp_path)


def test_writing_creates_only_the_path_it_was_given(tmp_path, measured_report):
    target = tmp_path / "nested" / "deeper" / "r.json"
    written = measured_report.write(target)
    assert written == target
    assert target.exists()
    # No stray files elsewhere in the tree.
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == ["r.json"]


# --------------------------------------------------------------- disclosure
def test_a_report_carries_no_environment_and_no_home_directory(measured_report):
    """A report is published. It must not carry the bench machine with it.

    The failure this prevents is mundane and common: a tool that helpfully
    records "the environment" and ships an API token to whoever reads the file.
    """
    serialised = canonical.canonical_json(measured_report.as_dict())
    assert "/home/" not in serialised
    assert "/root/" not in serialised
    for leaky in ("PATH", "TOKEN", "SECRET", "PASSWORD", "AWS_", "API_KEY"):
        assert leaky not in serialised


def test_the_report_carries_no_raw_samples_only_derived_figures(measured_report):
    """Sample series are not in the artefact.

    Partly size, partly discipline: a report is a summary that can be published,
    and the raw series belongs to whoever ran the bench.
    """
    assert "samples" not in measured_report.body
    for window in measured_report.body["windows"]:
        assert "samples" not in window
