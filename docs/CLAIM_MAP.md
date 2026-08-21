# Claim map

Every claim this project makes, where it is implemented, and the test that
proves it. Adding a claim adds a row plus its test. Deleting a test deletes the
row.

The point of the format: a claim with no test is marketing, and a test with no
claim is a test nobody will maintain.

---

## Claims that are enforced

| # | Claim | Implementation | Proven by |
|---|---|---|---|
| C-1 | A figure that was not measured cannot be exported as one | `energy_model.export_energy_model` | `test_a_synthetic_run_cannot_be_exported_as_a_measurement` |
| C-2 | Provenance comes from the instrument, never from the caller | `Report.from_run`, `SyntheticInstrument.identity` | `test_the_synthetic_instrument_declares_itself_synthetic` |
| C-3 | An exported synthetic figure carries its label permanently | `EnergyModelExport.source` | `test_a_synthetic_run_may_be_exported_but_carries_the_label` |
| C-4 | An edited report does not verify | `Report.verify`, `canonical.digest` | `test_an_edited_report_fails_verification_and_says_so` |
| C-5 | Verification shares no state with the writer | `Report.verify` reads only the file | `test_fr4_a_report_can_be_verified_by_someone_who_did_not_produce_it` |
| C-6 | An unknown schema is refused before the digest is believed | `Report.verify` | `test_an_unknown_schema_is_refused_before_the_digest_is_believed` |
| C-7 | Energy is integrated over actual timestamps | `metrics.integrate_energy` | `test_uneven_sample_spacing_is_respected` |
| C-8 | Non-monotonic timestamps are refused, not integrated | `metrics.integrate_energy` | `test_timestamps_going_backwards_are_refused` |
| C-9 | Fewer than two samples produce no figure | `metrics.integrate_energy` | `test_a_single_sample_is_refused_rather_than_extrapolated` |
| C-10 | The quoted per-operation figure excludes the idle floor | `Session.run`, `metrics.energy_above_idle` | `test_per_operation_energy_excludes_the_idle_floor` |
| C-11 | Every energy figure carries an error bar or declares none | `EnergyResult.joules_uncertainty` | `test_uncertainty_carries_both_the_rated_accuracy_and_the_resolution_floor` |
| C-12 | Quoted percentiles are latencies that occurred | `metrics._percentile`, nearest-rank | `test_percentiles_are_values_that_actually_occurred` |
| C-13 | One slow window is not a throttle | `thermal.assess_throttling`, consecutive rule | `test_one_slow_window_is_noise_not_a_throttle` |
| C-14 | A throttle verdict never claims a cause | `ThrottleVerdict.caveat` | `test_the_verdict_refuses_to_claim_a_cause` |
| C-15 | A driver that has not run against hardware refuses to read | `instruments.base.UnportedInstrument` | `test_an_unported_driver_refuses_to_open_and_says_what_is_missing` |
| C-16 | A reading before `open()` is an error, not a zero | `SyntheticInstrument.read` | `test_reading_before_opening_is_an_error_not_a_zero` |
| C-17 | Latency is timed by the harness, never self-reported | `Session.run` | `test_a_workloads_own_claims_do_not_reach_the_latency_figures` |
| C-18 | A run is reproducible from its seed | `SyntheticInstrument`, `ManualClock` | `test_the_run_is_reproducible_from_the_same_seed` |
| C-19 | The package never executes what it reads | source-level check | `test_the_package_never_evaluates_what_it_reads` |
| C-20 | A report carries no environment and no raw series | `Report.from_run` | `test_a_report_carries_no_environment_and_no_home_directory` |
| C-21 | Report size is bounded by windows, not samples | windows carry summaries | `test_a_long_run_does_not_retain_every_sample_in_the_artefact` |
| C-22 | The instrument is released even when the workload raises | `Session.run` `finally` | `test_the_instrument_is_closed_even_when_the_workload_explodes` |

## Claims deliberately not made

| Not claimed | Why | Demonstrated by |
|---|---|---|
| The instrument is accurate | Nothing in software can audit a meter that lies coherently | `test_an_instrument_that_understates_current_is_believed` (R-1) |
| A report proves who produced it | The digest detects editing, not authorship; nothing signs | `test_a_fully_recomputed_forgery_is_undetectable_from_the_file_alone` (R-2) |
| The declared conditions are true | `conditions` is free-form and unverified | R-3 in [THREAT_MODEL.md](THREAT_MODEL.md) |
| Threaded sampling achieves its target rate | It is at the mercy of the scheduler; `max_gap_s` shows the truth | R-4 |
| Two reports are comparable | Depends on instrument, sampler and conditions, all recorded | R-5 |
| Peak draw includes inrush | ~100 Hz sampling cannot see it | [METHOD.md](METHOD.md) §6 |
| Model load and warm-up are characterised | Excluded from both phases; not yet measured | [METHOD.md](METHOD.md) §6 |
