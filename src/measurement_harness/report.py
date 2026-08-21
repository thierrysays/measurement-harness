"""The artefact, and the one field a consumer must not skip.

A measurement report is only useful to somebody who was not in the room. That
means it has to carry the instrument, the conditions, the sampling strategy, the
error bar and — the field this module exists to make unavoidable — whether any
of it was actually measured.

The digest covers the body and excludes the identifier derived from it, so a
report can be verified by recomputing rather than trusted because it arrived.
There is no signature here: signing is an operator's key-management decision and
baking one in would make it on their behalf. What is provided is the shape a
signature would cover.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import canonical
from .errors import MeasurementError
from .session import RunResult

SCHEMA = "measurement-harness/report/v1"


@dataclass(frozen=True, slots=True)
class ReportProvenance:
    """Where the numbers came from. Read this before reading the numbers.

    ``kind`` is ``measured`` only when a real instrument was on a real rail.
    Everything else — a synthetic source, a replayed trace, a model — is
    ``synthetic``, and downstream code is expected to branch on it.
    """

    kind: str
    sampler: str
    harness_version: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "sampler": self.sampler,
            "harness_version": self.harness_version,
        }


@dataclass(frozen=True, slots=True)
class Report:
    """A complete run, serialisable and re-verifiable."""

    body: dict[str, Any]
    report_id: str

    # ------------------------------------------------------------------ making
    @classmethod
    def from_run(
        cls,
        run: RunResult,
        instrument_identity: dict[str, Any],
        workload: dict[str, Any],
        produced_at: str,
        harness_version: str,
    ) -> Report:
        provenance = ReportProvenance(
            kind=str(instrument_identity.get("provenance", "synthetic")),
            sampler=run.sampler_kind,
            harness_version=harness_version,
        )
        body: dict[str, Any] = {
            "schema": SCHEMA,
            "produced_at": produced_at,
            "provenance": provenance.as_dict(),
            "session": run.spec.as_dict(),
            "instrument": dict(instrument_identity),
            "workload": dict(workload),
            "idle": run.idle.as_dict(),
            "load": run.load.as_dict(),
            "latency": run.latency.as_dict(),
            "windows": [w.as_dict() for w in run.windows],
            "thermal": run.throttle.as_dict(),
            "operations": run.operations,
            "joules_per_operation": run.joules_per_operation,
            "joules_per_operation_above_idle": run.joules_per_operation_above_idle,
        }
        return cls(body=body, report_id=canonical.digest(body))

    # ----------------------------------------------------------------- reading
    @property
    def provenance(self) -> ReportProvenance:
        p = self.body["provenance"]
        return ReportProvenance(
            kind=p["kind"], sampler=p["sampler"], harness_version=p["harness_version"]
        )

    @property
    def is_measured(self) -> bool:
        return self.provenance.kind == "measured"

    def as_dict(self) -> dict[str, Any]:
        return {**self.body, "report_id": self.report_id}

    def write(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n")
        return p

    @classmethod
    def read(cls, path: str | Path) -> Report:
        raw = json.loads(Path(path).read_text())
        report_id = raw.pop("report_id", None)
        if report_id is None:
            raise ReportInvalid("report has no report_id")
        return cls(body=raw, report_id=str(report_id))

    # ---------------------------------------------------------------- checking
    def verify(self) -> None:
        """Recompute the digest. Raises :class:`ReportInvalid` on a mismatch.

        Shares no state with the writer beyond :mod:`~measurement_harness.canonical`,
        so this runs against a file on somebody else's machine.
        """
        if self.body.get("schema") != SCHEMA:
            raise ReportInvalid(
                f"unknown schema {self.body.get('schema')!r}; expected {SCHEMA!r}"
            )
        recomputed = canonical.digest(self.body)
        if recomputed != self.report_id:
            raise ReportInvalid(
                f"digest mismatch: file claims {self.report_id}, body hashes to {recomputed}"
            )


class ReportInvalid(MeasurementError):
    """The report on disk is not the report that was written."""

    code = "report-invalid"
