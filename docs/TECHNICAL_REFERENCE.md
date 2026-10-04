# Technical reference

What each module is, what it refuses, and the exact shape of every artefact.
[ARCHITECTURE.md](ARCHITECTURE.md) argues *why*; this is the file to keep open
while writing code against the package.

Package `measurement_harness`, distribution `measurement-harness`, console
script `mh`.

---

## Foundations

### `canonical.py`

Every digest is produced here or nowhere. JSON with sorted keys, `(",", ":")`
separators, `ensure_ascii=False`, `allow_nan=False`.

| Function | Returns | Refuses |
|---|---|---|
| `canonical_json(payload)` | `str` | `NaN`, `±inf`, at any depth |
| `digest(payload)` | `"sha256:<64 hex>"` | as above |

Key order does not affect the digest. Unicode is not normalised.

### `clock.py`

`Clock` protocol (`monotonic()` and `sleep()`) with `SystemClock` and
`ManualClock`. Nothing calls `time.monotonic()` directly. `ManualClock.sleep`
advances simulated time instead of blocking, which is what makes a six-minute
soak a unit test.

### `errors.py`

| Exception | `code` | Raised when |
|---|---|---|
| `MeasurementError` | `measurement-error` | base class |
| `InstrumentNotPresent` | `instrument-not-present` | the instrument could not be opened, or was read before opening |
| `NotPortedError` | `instrument-not-ported` | a driver exists as a declaration only |
| `InsufficientSamples` | `insufficient-samples` | fewer samples than the analysis needs |
| `SyntheticResultRefused` | `synthetic-result-refused` | a rehearsal was asked to stand in for a measurement |
| `ReportInvalid` | `report-invalid` | the file on disk is not the report that was written |

Codes are API. A wrapper that greps message text breaks on the first rewording.

---

## Instruments

### `instruments/base.py`

```python
class Instrument(Protocol):
    def identity(self) -> InstrumentIdentity: ...
    def open(self) -> None: ...
    def read(self, t_s: float) -> Sample: ...
    def close(self) -> None: ...
```

`Sample(t_s, volts, amps)`, power is derived, not stored, because a rail
sagging under load explains most throughput cliffs and is invisible in watts.

`InstrumentIdentity` carries `kind`, `description`, `provenance`
(`measured` | `synthetic`), `accuracy_pct`, `resolution_a`, `sample_rate_hz` and
a free-form `settings` dict for shunt value, address, gain, serial.

`UnportedInstrument`, subclass, set `identity_` and `porting_note`, and every
`open()`/`read()` raises `NotPortedError`.

### `instruments/synthetic.py`

Deterministic given a seed, and models an **averaging** meter: each reading is
the mean current since the previous reading, weighted by how much of that
interval was spent loaded. `SyntheticProfile` carries `idle_a`, `active_a`,
`volts`, `noise_a`, `ripple_a`, `ripple_hz`, `thermal_droop_pct_per_min`,
`sag_v`. `identity().provenance` is hard-coded to `synthetic`.

### `instruments/ina219.py`

Declared from the datasheet, drives nothing, raises. The module docstring is the
porting specification: high-side shunt, calibration register recorded in
`settings`, monotonic sampling with the timestamp actually achieved.

---

## Running a session

### `workload.py`

```python
class Workload(Protocol):
    def name(self) -> str: ...
    def describe(self) -> dict[str, Any]: ...
    def prepare(self) -> None: ...
    def invoke(self) -> None: ...      # exactly one unit of work
    def teardown(self) -> None: ...
```

`SyntheticWorkload` adds `latency_s`, `jitter_s`,
`thermal_slowdown_pct_per_min` and an injected clock.

### `session.py`

`SessionSpec`, `device`, `idle_s`, `windows`, `window_s`, `sample_interval_s`,
`throttle_threshold`, optional `thermometer`, free-form `conditions`.

`Sampler` protocol with two implementations:

| Sampler | Reads | Use |
|---|---|---|
| `InlineSampler` | between units of work | reproducible; blind to peak draw during one |
| `ThreadedSampler` | on a background thread at a target rate | real instruments; catches peaks; cannot use a simulated clock |

`Session.run()` returns `RunResult`: `spec`, `idle`, `load`, `latency`,
`windows`, `throttle`, `operations`, `joules_per_operation`,
`joules_per_operation_above_idle`, `sampler_kind`. The instrument is closed in a
`finally`, so a workload that raises still releases it.

### `metrics.py`

`integrate_energy(samples, identity) -> EnergyResult`, trapezoidal, over actual
timestamps. Raises on fewer than two samples and on non-monotonic time.
`EnergyResult` carries `joules`, `joules_uncertainty`, `mean_watts`,
`peak_watts`, `min_watts`, `duration_s`, `sample_count`, `max_gap_s`.

Uncertainty: `joules × accuracy_pct/100 + resolution_a × mean_volts × duration`.

`LatencySummary.from_latencies(...)`, nearest-rank percentiles, so every quoted
figure occurred. `energy_above_idle(result, idle_watts)`, clamped at zero.

### `thermal.py`

`Window(index, start_s, end_s, operations, mean_watts, mean_latency_s,
max_temperature_c)` with a derived `throughput_ops_s`.

`assess_throttling(windows, threshold=0.05, consecutive=2) -> ThrottleVerdict`.
The onset is the first window that, together with `consecutive` successors,
stays below threshold. The verdict carries a `caveat` string stating that
regression is observed, not attributed.

---

## Artefacts

### `measurement-harness/report/v1`

Written by `Report.from_run(...)`, verified by `Report.verify()`. `report_id` is
`sha256:<hex>` over the canonical form of every other key.

Full field list: [REPORT_FORMAT.md](REPORT_FORMAT.md).

### `measurement-harness/energy-model/v1`

Produced by `export_energy_model(report, actions, basis, allow_synthetic)`.

| Key | Meaning |
|---|---|
| `values` | action name → joules |
| `basis` | `above_idle` (default) or `total` |
| `source` | the sentence a consumer must carry verbatim |
| `uncertainty_j_per_operation` | load uncertainty ÷ operations |
| `report_id` | the report it came from |

Raises `SyntheticResultRefused` unless the report is `measured` or
`allow_synthetic=True`.

---

## Command line

| Command | Does | Exit codes |
|---|---|---|
| `mh run` | runs a session, writes a report, prints a summary | 0, or 2 on a `MeasurementError` |
| `mh show <report>` | prints the summary of an existing report | 0 |
| `mh verify <report>` | recomputes the digest | 0, or 2 on mismatch |
| `mh energy-model <report>` | prints the export as JSON | 0, or 2 if refused |

`mh run --instrument synthetic` uses a simulated clock by default so a soak
completes instantly; `--wall-clock` forces real time. A real instrument always
gets the real clock and a threaded sampler.

---

## Extending

**A new instrument**: implement the four methods, declare an identity, put it
behind an optional extra in `pyproject.toml` so that analysing a report never
requires a bus stack. If it has not run against hardware, subclass
`UnportedInstrument`.

**A new metric**: it belongs in `metrics.py` or `thermal.py`, must carry its own
uncertainty or state that it has none, and must appear in
[REPORT_FORMAT.md](REPORT_FORMAT.md) in the same change.

**A new artefact**: new schema identifier, new version, never an edit to an
existing one, both identifiers are inside hashed bodies.
