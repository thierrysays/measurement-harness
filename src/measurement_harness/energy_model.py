"""Exporting a per-action energy figure for whoever needs one downstream.

Plenty of systems carry a table of "how much does this action cost" and populate
it with an educated guess. The guess is usually fine and occasionally out by an
order of magnitude, and nothing in the system distinguishes the two cases.

This module is the bridge from a run to such a table, and it has one rule: a
figure derived from a synthetic run is not allowed to leave here wearing the
label of a measurement. The caller may have one anyway — rehearsing a pipeline
is legitimate — but only by asking in as many words, and the exported ``source``
string then says ``synthetic`` for as long as the figure lives.

The default basis is energy **above idle**. A per-action figure that includes the
idle floor is really a figure about the duty cycle of the run that produced it,
and will be wrong for any deployment with a different one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import SyntheticResultRefused
from .report import Report

BASIS_ABOVE_IDLE = "above_idle"
BASIS_TOTAL = "total"


@dataclass(frozen=True, slots=True)
class EnergyModelExport:
    """A table of joules per action, and the sentence that qualifies it."""

    values: dict[str, float]
    source: str
    basis: str
    uncertainty_j_per_operation: float
    report_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "measurement-harness/energy-model/v1",
            "values": dict(self.values),
            "source": self.source,
            "basis": self.basis,
            "uncertainty_j_per_operation": self.uncertainty_j_per_operation,
            "report_id": self.report_id,
        }


def export_energy_model(
    report: Report,
    actions: Mapping[str, float] | None = None,
    basis: str = BASIS_ABOVE_IDLE,
    allow_synthetic: bool = False,
) -> EnergyModelExport:
    """Derive a per-action energy table from one run.

    ``actions`` maps an action name to a multiplier of the measured per-operation
    figure — ``{"inference": 1.0, "inference_batch4": 4.0}``. Multipliers are the
    caller's assertion about their own system, and the export says so: only the
    ``1.0`` entries are measured, the rest are scaled from a measurement.
    """
    if basis not in (BASIS_ABOVE_IDLE, BASIS_TOTAL):
        raise ValueError(f"unknown basis {basis!r}")

    if not report.is_measured and not allow_synthetic:
        raise SyntheticResultRefused(
            f"report {report.report_id} has provenance "
            f"{report.provenance.kind!r}; pass allow_synthetic=True to export a "
            "rehearsal figure, which will be labelled as one"
        )

    per_op = (
        report.body["joules_per_operation_above_idle"]
        if basis == BASIS_ABOVE_IDLE
        else report.body["joules_per_operation"]
    )
    actions = actions or {"inference": 1.0}
    values = {name: per_op * float(scale) for name, scale in actions.items()}

    operations = max(1, int(report.body["operations"]))
    uncertainty = float(report.body["load"]["joules_uncertainty"]) / operations

    instrument = report.body["instrument"]
    session = report.body["session"]
    thermal = report.body["thermal"]
    qualifier = "measured" if report.is_measured else "synthetic — not measured"
    throttle_note = (
        f", throughput regressed {thermal['regression']:.1%} under sustained load"
        if thermal.get("throttled")
        else ""
    )
    source = (
        f"{qualifier} — {instrument['kind']} on {session['device']}, "
        f"{operations} operations, basis {basis}, report {report.report_id}"
        f"{throttle_note}"
    )
    scaled = sorted(n for n, s in actions.items() if float(s) != 1.0)
    if scaled:
        source += f"; scaled (not measured) for: {', '.join(scaled)}"

    return EnergyModelExport(
        values=values,
        source=source,
        basis=basis,
        uncertainty_j_per_operation=uncertainty,
        report_id=report.report_id,
    )
