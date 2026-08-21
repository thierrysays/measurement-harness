# Functional specification

What this harness does, for whom, and what counts as it working. Written so that
someone who will never read the source can tell whether a claim made about a
figure it produced is true.

The technical counterpart is [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md).
Every requirement below is discharged by a named test in
`tests/functional/test_requirements.py`.

---

## Purpose

Characterise a device under sustained load, and emit an artefact that carries
the figures **together with everything needed to judge them**: the instrument,
the conditions, the sampling strategy, the error bar, and whether any of it was
measured at all.

Explicitly **not** in scope: ranking devices, benchmarking models, certifying
efficiency claims, or deciding whether a workload should run.

## Actors

| Actor | Does | Cannot |
|---|---|---|
| **Bench operator** | Wires the instrument, declares the conditions, runs the session | Make a synthetic run export as measured |
| **Instrument** | Reports volts and amps when asked | Be audited by the harness — see R-1 |
| **Workload** | Performs one unit of work per `invoke()` | Supply its own latency figures |
| **Report consumer** | Reads a report, verifies its digest, uses the export | Be required to trust the machine that wrote it, for *integrity* |
| **Downstream system** | Copies an energy figure into its own table | Receive a number without the sentence qualifying it |

The separation that matters: **the thing being measured never contributes to the
measurement.** Latency comes from the harness's own clock around `invoke()`;
energy comes from the instrument, not from the workload's opinion of itself.

## Preconditions

A session may produce a report only if all of these hold. Each failure is a
refusal with a code, not a warning.

1. The instrument opens. An instrument that is absent raises
   `InstrumentNotPresent`; an instrument that has never run against hardware
   raises `NotPortedError`.
2. At least two samples exist for any window being integrated.
3. Sample timestamps are non-decreasing.
4. Every figure is finite. A run that produced `NaN` produced nothing.
5. At least two windows exist before a throttle verdict is reached.

---

## Functional requirements

### FR-1 — A report states the conditions it was taken under

Instrument identity, session specification, ambient conditions, sampler kind and
harness version are all present in every report.

*Verified by* `test_fr1_a_run_records_the_conditions_it_was_taken_under`.

### FR-2 — The quoted energy figure excludes the idle floor

An idle baseline is measured before the workload is prepared. The headline
per-operation figure is energy **above idle**; the total is also present, and
larger.

*Verified by* `test_fr2_the_quoted_figure_excludes_the_idle_floor`.

### FR-3 — Sustained load is windowed and assessed

The load phase is divided into equal windows, each carrying its own throughput,
mean power, mean latency and peak temperature. A verdict compares the first
window against the sustained tail.

*Verified by* `test_fr3_a_sustained_run_is_windowed_and_assessed` and
`test_fr3_a_run_that_holds_its_throughput_is_not_flagged`.

### FR-4 — A report can be verified by someone who did not produce it

`mh verify` recomputes the digest over the canonical form of the body. It shares
no state with the writer beyond the canonicalisation rules, and exits non-zero on
a mismatch.

*Verified by* `test_fr4_a_report_can_be_verified_by_someone_who_did_not_produce_it`
and `test_fr4_verification_fails_loudly_on_an_altered_report`.

### FR-5 — A synthetic run cannot be exported as a measurement

`mh energy-model` refuses a report whose provenance is not `measured`. With
`--allow-synthetic` it proceeds, and the exported `source` says
`synthetic — not measured`.

*Verified by* `test_fr5_a_synthetic_run_cannot_be_exported_as_a_measurement`.

### FR-6 — An unported instrument refuses rather than inventing readings

A driver written from a datasheet and never run against the part raises, and no
report is written.

*Verified by* `test_fr6_an_instrument_that_has_never_run_refuses_to_produce_readings`.

### FR-7 — A run is reproducible from its inputs

The same seed, spec and workload produce the same figures and the same report
identifier.

*Verified by* `test_fr7_the_same_inputs_produce_the_same_figures` and
`test_fr7_two_identical_runs_digest_identically`.

### FR-8 — Every energy figure carries an error bar

Rated accuracy as a proportional term, resolution as an absolute floor. An
instrument that declares neither gets zero, and the instrument block shows why.

*Verified by* `test_fr8_a_report_carries_an_error_bar_or_says_it_has_none`.

### FR-9 — The export carries the sentence, not just the number

`source` names the instrument, the device, the operation count, the basis, the
originating report digest, whether throughput regressed, and which actions were
scaled rather than measured.

*Verified by* `test_fr9_the_export_carries_the_sentence_not_just_the_number` and
`test_fr9_a_scaled_action_is_never_described_as_measured`.

### FR-10 — A report round-trips through a file unchanged

Writing and reading does not change what a report says or what it digests to.

*Verified by* `test_fr10_a_report_round_trips_through_a_file_unchanged`.

---

## Acceptance criteria

The harness is working when all of the following hold on a machine with no
instrument attached:

```
make smoke      # starts, runs, writes a parseable report
make test       # every tier green
make demo       # a six-minute soak in simulated time, verdict printed
make qa         # lint, strict types, SAST, dependency advisories, coverage
```

and `mh energy-model ./run/report.json` exits non-zero with
`synthetic-result-refused`, because nothing was measured.

## Non-functional requirements

| # | Requirement | How it is met |
|---|---|---|
| NFR-1 | Installs on an awkward machine | No runtime dependencies |
| NFR-2 | A soak test is testable | Injectable clock; `ManualClock` runs six minutes instantly |
| NFR-3 | A report is publishable | Digests and summaries only, no raw series, no environment |
| NFR-4 | Failures are machine-readable | One exception per mode, each with a stable `code` |
| NFR-5 | Report size is bounded by windows, not by samples | Windows carry summaries |

## Out of scope, deliberately

- **Signing.** The report has the shape a signature would cover; choosing a key
  story belongs to whoever runs the bench. See R-2 in
  [THREAT_MODEL.md](THREAT_MODEL.md).
- **Calibration.** The uncertainty is propagated from what the instrument claims
  about itself. A meter that lies produces an error bar that lies. R-1.
- **Model-load characterisation.** Excluded from both baseline and load window,
  and not currently measured as its own phase. Stated in
  [METHOD.md](METHOD.md).
- **Inrush.** Sampling at around 100 Hz cannot see it.
