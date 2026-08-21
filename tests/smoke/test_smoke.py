"""Smoke: does the thing start at all.

Runs in under a second, imports nothing clever, and is what you run after an
install on a machine you have never used before. If these fail, nothing further
down the pyramid is worth reading.

Marked ``smoke`` so `make smoke` can select them without collecting the rest.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

pytestmark = pytest.mark.smoke


def test_the_package_imports():
    import measurement_harness

    assert measurement_harness.__version__


def test_the_public_surface_is_importable_from_the_top_level():
    from measurement_harness import Report, Session, SessionSpec  # noqa: F401


def test_the_console_entry_point_answers(tmp_path, cli_env):
    result = subprocess.run(
        [sys.executable, "-m", "measurement_harness.cli", "--version"],
        capture_output=True, text=True, cwd=tmp_path, env=cli_env,
    )
    assert result.returncode == 0
    assert "measurement-harness" in result.stdout


def test_a_minimal_run_produces_a_file_that_parses(tmp_path, cli_env):
    out = tmp_path / "smoke.json"
    result = subprocess.run(
        [sys.executable, "-m", "measurement_harness.cli", "run",
         "--device", "smoke", "--windows", "2", "--window-s", "2",
         "--idle-s", "1", "--out", str(out)],
        capture_output=True, text=True, cwd=tmp_path, env=cli_env,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text())
    assert payload["schema"] == "measurement-harness/report/v1"
    assert payload["report_id"].startswith("sha256:")


def test_the_help_text_lists_every_subcommand(cli_env):
    result = subprocess.run(
        [sys.executable, "-m", "measurement_harness.cli", "--help"],
        capture_output=True, text=True, env=cli_env,
    )
    for command in ("run", "show", "verify", "energy-model"):
        assert command in result.stdout
