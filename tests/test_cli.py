"""The command line, exercised end to end on the synthetic path."""

import json

import pytest

from measurement_harness.cli import main


def test_run_writes_a_verifiable_report(tmp_path, capsys):
    out = tmp_path / "r.json"
    assert main(["run", "--device", "board-x", "--windows", "3", "--window-s", "10",
                 "--idle-s", "2", "--out", str(out)]) == 0
    assert main(["verify", str(out)]) == 0
    assert "report_id verified" in capsys.readouterr().out


def test_verify_fails_loudly_on_an_edited_report(tmp_path):
    out = tmp_path / "r.json"
    main(["run", "--device", "board-x", "--windows", "2", "--window-s", "5",
          "--idle-s", "1", "--out", str(out)])
    raw = json.loads(out.read_text())
    raw["operations"] += 1
    out.write_text(json.dumps(raw))
    assert main(["verify", str(out)]) == 2


def test_energy_model_refuses_a_synthetic_report_by_default(tmp_path, capsys):
    out = tmp_path / "r.json"
    main(["run", "--device", "board-x", "--windows", "2", "--window-s", "5",
          "--idle-s", "1", "--out", str(out)])
    assert main(["energy-model", str(out)]) == 2
    assert "synthetic-result-refused" in capsys.readouterr().err


def test_energy_model_emits_json_when_synthetic_is_allowed(tmp_path, capsys):
    out = tmp_path / "r.json"
    main(["run", "--device", "board-x", "--windows", "2", "--window-s", "5",
          "--idle-s", "1", "--out", str(out)])
    capsys.readouterr()
    assert main(["energy-model", str(out), "--allow-synthetic"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "measurement-harness/energy-model/v1"
    assert "inference" in payload["values"]
    assert "not measured" in payload["source"]


def test_a_slowing_workload_is_reported_as_throttled(tmp_path, capsys):
    out = tmp_path / "r.json"
    main(["run", "--device", "board-x", "--windows", "5", "--window-s", "30",
          "--idle-s", "2", "--slowdown", "25", "--out", str(out)])
    assert "THROTTLED" in capsys.readouterr().out
    assert json.loads(out.read_text())["thermal"]["throttled"] is True


def test_an_unported_instrument_stops_the_run(tmp_path):
    with pytest.raises(SystemExit):
        main(["run", "--device", "board-x", "--instrument", "nonexistent",
              "--out", str(tmp_path / "r.json")])
    assert main(["run", "--device", "board-x", "--instrument", "ina219",
                 "--windows", "1", "--window-s", "1", "--idle-s", "1",
                 "--out", str(tmp_path / "r.json")]) == 2


def test_show_prints_a_summary_without_recomputing_anything(tmp_path, capsys):
    out = tmp_path / "r.json"
    main(["run", "--device", "board-x", "--windows", "2", "--window-s", "5",
          "--idle-s", "1", "--out", str(out)])
    capsys.readouterr()
    assert main(["show", str(out)]) == 0
    assert "board-x" in capsys.readouterr().out
