# Threat model

Who this defends against, who it does not, and where the line is. Every claim
below is either pinned by a test in `tests/security/` and `tests/pentest/`, or
listed as residual.

This is a measurement tool, not a security product. The threat that matters is
not intrusion; it is **a wrong number being believed**.

---

## Assets

| Asset | Why it is worth attacking |
|---|---|
| The **report** | It is the evidence. Altering it changes what a device is believed to cost |
| The **provenance field** | Flipping it turns a rehearsal into a measurement |
| The **instrument identity** | A better-sounding meter shrinks the error bar and wins comparisons |
| The **energy-model export** | It is what reaches other systems, where it loses context |

## Adversaries

| # | Adversary | Capability assumed |
|---|---|---|
| **P1** | A motivated author | Can edit report files and run the harness. Wants a better figure |
| **P2** | A hostile instrument or workload | Controls what the harness reads. A vendor SDK, a supplied driver |
| **P3** | A careless consumer | Copies `values` and drops `source`. Not malicious, and the most common |

---

## What is defended, and by what

### P1 — the author edits the file

| Attack | Control | Pinned by |
|---|---|---|
| Relabel a synthetic run as measured | Digest covers `provenance` | `test_relabelling_a_synthetic_run_as_measured_breaks_the_digest` |
| Inflate the operation count to shrink energy per operation | Digest covers `operations` | `test_inflating_the_operation_count_to_shrink_energy_per_op_is_caught` |
| Attribute the run to a more accurate meter | Digest covers the instrument block | `test_upgrading_the_instrument_to_shrink_the_error_bar_is_caught` |
| Delete an inconvenient throttle verdict | Digest covers `thermal` | `test_deleting_the_throttle_verdict_is_caught` |
| Lift a valid identifier from another report | The identifier is over *this* body | `test_a_report_id_lifted_from_another_report_does_not_verify` |
| Reorder keys to disguise an edit | Canonical serialisation | `test_reordering_keys_does_not_forge_a_different_report` |
| Present a report under a schema the reader does not know | Schema checked before the digest is believed | `test_an_unknown_schema_is_refused_before_the_digest_is_believed` |

### P2 — the instrument or workload lies

| Attack | Control | Pinned by |
|---|---|---|
| A workload reports its own flattering latency | Latency is timed by the harness around `invoke()` | `test_a_workloads_own_claims_do_not_reach_the_latency_figures` |
| An instrument returns `NaN` to poison the figures | Canonicalisation refuses non-finite values; no report is written | `test_an_instrument_returning_nan_cannot_produce_a_report` |
| An instrument stamps readings out of order to inflate duration | Integration refuses non-monotonic timestamps | `test_readings_stamped_out_of_order_are_refused_not_integrated` |
| A driver returns plausible numbers without hardware | `UnportedInstrument` raises | `test_an_unported_driver_refuses_to_open_and_says_what_is_missing` |
| An instrument is read before it is opened | `InstrumentNotPresent` | `test_reading_before_opening_is_an_error_not_a_zero` |

### P3 — the consumer drops the qualification

| Attack | Control | Pinned by |
|---|---|---|
| A synthetic figure reaches a downstream table | Export refuses unless asked explicitly | `test_fr5_a_synthetic_run_cannot_be_exported_as_a_measurement` |
| A scaled figure is described as measured | `source` names every scaled action | `test_fr9_a_scaled_action_is_never_described_as_measured` |
| A throttled run is quoted as steady state | `source` carries the regression | `test_a_throttled_run_says_so_in_the_source_string` |

### The process itself

| Attack | Control | Pinned by |
|---|---|---|
| A report that executes on load | No `eval`, `exec`, `pickle`, `subprocess` anywhere in the package | `test_the_package_never_evaluates_what_it_reads` |
| A deeply nested file taking the process down | Raises catchably | `test_deeply_nested_input_raises_rather_than_taking_the_process_down` |
| A report leaking the bench machine | No environment, no home paths in the artefact | `test_a_report_carries_no_environment_and_no_home_directory` |
| A soak producing an unopenable artefact | Report size is bounded by windows, not samples | `test_a_long_run_does_not_retain_every_sample_in_the_artefact` |

---

## Residual risks

Accepted, not deferred. Each is pinned by a test that demonstrates the gap.

### R-1 — The harness cannot audit its instrument

A driver that halves every reading produces a report that verifies and exports
as measured. No software control detects it. The mitigation is a bench
procedure: calibrate against a second meter, on a known load, and record both in
`conditions`.

*Pinned by* `test_an_instrument_that_understates_current_is_believed`.

### R-2 — A fully recomputed forgery is undetectable from the file alone

The digest detects editing, not authorship. Anyone who edits a report *and*
recomputes the identifier produces a file that verifies. Nothing here signs,
because choosing a key story belongs to whoever runs the bench.

Closing it means a signature over the report body — the shape is already there,
`report_id` is over everything else — plus a trust store on the reader's side.
Until then, a report is evidence to somebody who trusts the bench.

*Pinned by* `test_a_fully_recomputed_forgery_is_undetectable_from_the_file_alone`.

### R-3 — Conditions are declared, not observed

`conditions` is free-form and unverified. Ambient temperature, cooling and
firmware version are whatever the operator typed. A run taken in a cold room can
be labelled as one taken in a warm one.

### R-4 — Threaded sampling is at the mercy of the scheduler

`ThreadedSampler` targets a rate and does not guarantee it. Under load its gaps
widen, which is visible in `max_gap_s` and nowhere else. Sample-rate starvation
degrades the integral silently in the sense that nothing refuses; it degrades it
*visibly* in the sense that the field is in the report.

### R-5 — Comparability across reports is the reader's problem

Two reports with different samplers, instruments or conditions may not be
comparable. The harness records all three and refuses nothing, because sometimes
the comparison is exactly right and the harness does not know when.

---

## Claims deliberately not made

- **Not tamper-proof.** Tamper-*evident*, and only against editing (R-2).
- **Not calibrated.** Uncertainty is propagated from declarations, not measured
  against a reference (R-1).
- **Not a security boundary.** A hostile instrument that returns coherent lies
  wins, and always will.
- **Not an attestation of the device under test.** A report says what a bench
  observed. It does not say what board was on the bench.
