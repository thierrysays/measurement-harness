# ADR 0002 — A synthetic run cannot be exported as a measurement

**Status:** accepted · 2026-08-21

## Context

The harness must be usable before any instrument exists, or it will be shaped by
whatever the first meter made easy. That means a synthetic source producing
plausible numbers — and plausible numbers, once written to a file, get believed.

The failure is not hypothetical: an estimate propagated into a downstream table,
carried through two systems, and quoted back as a measured figure is how most
bad energy numbers in this field come to exist.

## Decision

`provenance.kind` is carried on every report and derived from the instrument,
not asserted by the caller. `export_energy_model` raises
`SyntheticResultRefused` on a report that is not `measured`. The caller may pass
`allow_synthetic=True`, and the exported `source` string then reads
`synthetic — not measured` permanently.

## Cost

An extra argument in the one workflow where a rehearsal figure is genuinely
wanted, and a class of report that cannot be silently reused. Both are the
point.

## Consequence

`SyntheticInstrument.identity()` hard-codes `provenance="synthetic"`. Nothing in
the source tree can produce a report claiming to be measured without a real
instrument; the only place that claim is manufactured is a test fixture, named
as one.
