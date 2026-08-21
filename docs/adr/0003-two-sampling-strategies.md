# ADR 0003 — Two samplers, and the report says which

**Status:** accepted · 2026-08-21

## Context

An inline sampler reads between units of work. It is exactly reproducible, it
composes with a simulated clock, and it makes a six-minute soak test run inside
a unit suite. It is also structurally blind to the peak draw of the inference
itself, because by construction it never reads during one.

A threaded sampler reads at a target rate regardless of what the workload is
doing, and catches the peak. It cannot be driven by a simulated clock, so it
cannot be used in the test suite, and its timing is at the mercy of the
scheduler on a loaded machine.

## Decision

Ship both. Default to inline for synthetic runs and threaded for real
instruments. Record `provenance.sampler` in every report.

## Cost

Two code paths for sampling, and two classes of report whose `peak_watts` must
not be compared. The alternative — one sampler — meant either an untestable
harness or a harness that cannot see peaks, and both were worse.

## Consequence

Any comparison across reports has to check `provenance.sampler` first. The
field exists so that a reader can, rather than so that the harness can refuse
the comparison on their behalf: comparing a threaded and an inline report is
sometimes exactly right, and the harness does not know when.
