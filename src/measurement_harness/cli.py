"""Command line: produce a report, read one, check one, export from one.

Producing evidence and checking evidence are separate commands on purpose. A
tool that verifies its own output as part of producing it has verified nothing
that an auditor cares about.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timezone

from . import __version__
from .clock import Clock, ManualClock, SystemClock
from .energy_model import BASIS_ABOVE_IDLE, BASIS_TOTAL, export_energy_model
from .errors import MeasurementError
from .instruments.base import Instrument
from .instruments.ina219 import INA219Instrument
from .instruments.synthetic import SyntheticInstrument, SyntheticProfile
from .report import Report
from .session import InlineSampler, Session, SessionSpec, ThreadedSampler
from .workload import SyntheticWorkload


def _build_instrument(
    name: str, seed: int, droop: float, clock: Clock
) -> Instrument:
    if name == "synthetic":
        return SyntheticInstrument(
            SyntheticProfile(thermal_droop_pct_per_min=droop), seed=seed, clock=clock
        )
    if name == "ina219":
        return INA219Instrument()
    raise SystemExit(f"unknown instrument {name!r}; known: synthetic, ina219")


def cmd_run(args: argparse.Namespace) -> int:
    # A synthetic run uses simulated time so a six-minute soak completes at once.
    # A real instrument gets the real clock, and takes as long as it takes.
    simulated = args.instrument == "synthetic" and not args.wall_clock
    clock = ManualClock() if simulated else SystemClock()
    sampler = InlineSampler() if simulated else ThreadedSampler(args.sample_interval)

    instrument = _build_instrument(args.instrument, args.seed, args.droop, clock)
    workload = SyntheticWorkload(
        latency_s=args.latency_ms / 1000.0,
        thermal_slowdown_pct_per_min=args.slowdown,
        clock=clock,
        model=args.model,
    )
    spec = SessionSpec(
        device=args.device,
        idle_s=args.idle_s,
        windows=args.windows,
        window_s=args.window_s,
        sample_interval_s=args.sample_interval,
        throttle_threshold=args.threshold,
        conditions={"ambient_c": args.ambient} if args.ambient is not None else {},
    )

    result = Session(instrument, workload, spec, clock=clock, sampler=sampler).run()
    report = Report.from_run(
        result,
        instrument_identity=instrument.identity().as_dict(),
        workload=workload.describe(),
        produced_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        harness_version=__version__,
    )
    path = report.write(args.out)
    _print_summary(report)
    print(f"\n  written: {path}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    _print_summary(Report.read(args.report))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    report = Report.read(args.report)
    report.verify()
    print(f"report_id verified: {report.report_id}")
    print(f"provenance        : {report.provenance.kind}")
    return 0


def cmd_energy_model(args: argparse.Namespace) -> int:
    report = Report.read(args.report)
    report.verify()
    actions = {name: 1.0 for name in args.action}
    export = export_energy_model(
        report,
        actions=actions,
        basis=BASIS_TOTAL if args.total else BASIS_ABOVE_IDLE,
        allow_synthetic=args.allow_synthetic,
    )
    print(json.dumps(export.as_dict(), indent=2, sort_keys=True))
    return 0


def _print_summary(report: Report) -> None:
    b = report.body
    t = b["thermal"]
    lat = b["latency"]
    print(f"  device       : {b['session']['device']}")
    print(f"  instrument   : {b['instrument']['kind']} ({b['provenance']['kind']})")
    print(f"  sampler      : {b['provenance']['sampler']}")
    print(f"  operations   : {b['operations']}")
    print(f"  idle         : {b['idle']['mean_watts']:.3f} W")
    print(f"  load         : {b['load']['mean_watts']:.3f} W mean, "
          f"{b['load']['peak_watts']:.3f} W peak")
    per_op_uncertainty_mj = (
        b["load"]["joules_uncertainty"] / max(1, b["operations"]) * 1000
    )
    print(f"  energy/op    : {b['joules_per_operation_above_idle'] * 1000:.3f} mJ "
          f"above idle (± {per_op_uncertainty_mj:.3f} mJ)")
    print(f"  latency      : p50 {lat['p50_s'] * 1000:.1f} ms, "
          f"p95 {lat['p95_s'] * 1000:.1f} ms, p99 {lat['p99_s'] * 1000:.1f} ms")
    verdict = "THROTTLED" if t["throttled"] else "held"
    onset = f" from t={t['onset_s']:.0f}s" if t["onset_s"] is not None else ""
    print(f"  sustained    : {verdict}{onset}, "
          f"{t['first_window_ops_s']:.1f} -> {t['sustained_ops_s']:.1f} ops/s "
          f"({-t['regression']:+.1%} throughput)")
    print(f"  report_id    : {report.report_id}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mh", description=__doc__.splitlines()[0])
    p.add_argument("--version", action="version", version=f"measurement-harness {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="run a measurement session and write a report")
    r.add_argument("--device", required=True, help="free-form device-under-test id")
    r.add_argument("--instrument", default="synthetic", help="synthetic | ina219")
    r.add_argument("--out", default="./report.json")
    r.add_argument("--idle-s", type=float, default=10.0, dest="idle_s")
    r.add_argument("--windows", type=int, default=6)
    r.add_argument("--window-s", type=float, default=60.0, dest="window_s")
    r.add_argument("--sample-interval", type=float, default=0.05)
    r.add_argument("--threshold", type=float, default=0.05)
    r.add_argument("--latency-ms", type=float, default=20.0)
    r.add_argument("--slowdown", type=float, default=0.0,
                   help="synthetic workload slowdown, %% per minute")
    r.add_argument("--droop", type=float, default=0.0,
                   help="synthetic current droop, %% per minute")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--model", default="synthetic/none")
    r.add_argument("--ambient", type=float, default=None, help="ambient temperature, C")
    r.add_argument("--wall-clock", action="store_true",
                   help="run a synthetic session in real time rather than simulated")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("show", help="print a human summary of a report")
    s.add_argument("report")
    s.set_defaults(func=cmd_show)

    v = sub.add_parser("verify", help="recompute a report's digest")
    v.add_argument("report")
    v.set_defaults(func=cmd_verify)

    e = sub.add_parser("energy-model", help="export joules per action from a report")
    e.add_argument("report")
    e.add_argument("--action", action="append", default=None,
                   help="action name; repeatable (default: inference)")
    e.add_argument("--total", action="store_true",
                   help="use total energy rather than energy above idle")
    e.add_argument("--allow-synthetic", action="store_true",
                   help="permit export from a synthetic run, labelled as one")
    e.set_defaults(func=cmd_energy_model)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "action", None) is None and args.command == "energy-model":
        args.action = ["inference"]
    try:
        return int(args.func(args))
    except MeasurementError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
