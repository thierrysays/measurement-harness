# `measurement-harness/report/v1`

The artefact. One JSON object per run, digested over its canonical form.

## Verification

`report_id` is `sha256:<hex>` over the canonical serialisation of every other
key: sorted keys, compact separators, non-finite floats refused. Recompute it
with `mh verify <path>`; the check shares no state with the writer beyond the
canonicalisation rules, so it runs against a file on someone else's machine.

There is no signature. Signing is a key-management decision belonging to whoever
operates the bench, and baking one choice in would make it on their behalf. What
is provided is the shape a signature would cover.

## Fields

| Key | Meaning |
|---|---|
| `schema` | `measurement-harness/report/v1`. Refused if unrecognised, before the digest is trusted. |
| `produced_at` | ISO-8601 UTC, from the machine that ran the session. |
| `provenance.kind` | `measured` or `synthetic`. **Read this first.** |
| `provenance.sampler` | `inline` or `threaded`. Peak figures are not comparable across the two. |
| `provenance.harness_version` | Version of the harness that produced the run. |
| `session` | The spec: device string, idle seconds, window count and length, sample interval, throttle threshold, whether a thermometer was present, free-form conditions. |
| `instrument` | Kind, description, provenance, rated accuracy, resolution, sample rate, and driver settings, shunt value, address, gain. |
| `workload` | Whatever the workload's `describe()` returned. Opaque to the harness. |
| `idle` | Energy result over the idle baseline. |
| `load` | Energy result over the whole sustained run. |
| `latency` | Count, mean, min, p50, p90, p95, p99, max, standard deviation, in seconds. |
| `windows[]` | Per window: index, start, end, operations, throughput, mean watts, mean latency, peak temperature. |
| `thermal` | The throttle verdict, its threshold, the onset, the first-window and sustained rates, temperature rise, and the caveat about attribution. |
| `operations` | Total units of work. |
| `joules_per_operation` | Total energy divided by operations. Includes the idle floor. |
| `joules_per_operation_above_idle` | The figure to quote. Idle floor removed. |

An energy result (`idle` and `load`) carries `joules`, `joules_uncertainty`,
`mean_watts`, `peak_watts`, `min_watts`, `duration_s`, `sample_count` and
`max_gap_s`.

## `measurement-harness/energy-model/v1`

The export produced by `mh energy-model`, for systems that carry a per-action
energy table.

```json
{
  "schema": "measurement-harness/energy-model/v1",
  "basis": "above_idle",
  "values": { "inference": 0.0699 },
  "source": "measured — ina219 on uno-q, 12207 operations, basis above_idle, report sha256:…",
  "uncertainty_j_per_operation": 0.00035,
  "report_id": "sha256:…"
}
```

`values` are joules. `basis` is `above_idle` (default) or `total`. `source` is a
sentence intended to be carried verbatim by the consumer: it names the
instrument, the device, the operation count, the basis, the originating report,
and (where relevant) that throughput regressed under sustained load, or that
an action's figure was scaled from a measurement rather than measured.

A consumer that keeps `values` and discards `source` has kept the number and
thrown away the part that says how much to believe it.

## Compatibility

Both identifiers are frozen. `measurement-harness/report/v1` appears inside the
hashed body, so changing the string invalidates every report ever produced.
A breaking change gets `/v2` and a new file, not an edit.
