"""The only place a report is serialised for hashing.

A digest is worth exactly as much as the determinism of the bytes beneath it.
Sorted keys, no insignificant whitespace, and non-finite floats rejected outright,
a report containing ``NaN`` is a report whose digest depends on which JSON
encoder the reader happens to use.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def _reject_non_finite(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(
            f"non-finite float {value!r} cannot be canonicalised; "
            "a measurement that produced NaN or inf is a measurement that failed"
        )
    if isinstance(value, dict):
        return {k: _reject_non_finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_reject_non_finite(v) for v in value]
    return value


def canonical_json(payload: Any) -> str:
    """Deterministic JSON: sorted keys, compact separators, finite floats only."""
    return json.dumps(
        _reject_non_finite(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest(payload: Any) -> str:
    """``sha256:<hex>`` over the canonical form."""
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
