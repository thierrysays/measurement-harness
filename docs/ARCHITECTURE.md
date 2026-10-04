# Architecture

Why the harness is shaped this way. The what is in
[TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md); this file is the argument.

---

## The problem with published figures

Almost every efficiency number in edge AI is a burst figure. A model is loaded,
one inference is timed, a wattage is quoted from a datasheet or a smart plug,
and the whole thing happens in the first thirty seconds while the board is cold.

Deployments are not cold. Under continuous inference a passively-cooled SoC
reaches its thermal limit within minutes, the governor pulls the clock back, and
steady-state throughput settles somewhere below the number that was published.
The gap between burst and steady state is the operationally interesting figure,
and it is the one almost nobody measures, because measuring it takes six
minutes per configuration instead of six seconds, and because the result is
worse.

Three consequences shape everything here.

## 1. The run is long, and it is windowed

A single measurement produces a number with no way to tell whether it was taken
before or after the part warmed up. So the unit of measurement is a **sustained
run divided into windows**, and the report carries every window rather than an
average across them. An average across a throttling run is a figure that
describes no moment of it.

The consequence is that the harness must be able to run for six minutes in a
test suite. Hence the injectable clock, and hence `ManualClock`, which makes a
soak test complete in microseconds while producing exactly the timestamps the
real run would have produced.

## 2. The instrument is a stranger

The core never learns what it is driving. `open`, `read`, `close`, and an
identity block.

Two reasons. The first is portability: a shunt monitor over I²C, a bench supply
over SCPI, a USB-C inline analyser and a smart plug on the mains side of a DC
brick all satisfy the same contract, and the analysis path should not fork per
meter. The second is honesty about where trust lives, the harness cannot audit
its instrument, so the best it can do is record precisely which one produced the
figures, with what rated accuracy and what wiring, and let a reader judge.

This is also why the identity block is not optional decoration. A power figure
without its instrument is a number, and two boards cannot be compared across a
difference the meter cannot resolve.

## 3. Provenance is structural, not a convention

The one property the harness actually enforces is that a figure that was not
measured never leaves labelled as one.

It would have been easy to make this a convention, a flag in a config file, a
note in a README. Conventions decay across system boundaries, and the boundary
is exactly where the damage happens: an estimate copied into a downstream table,
carried through two systems, and quoted back as a measurement, with nothing in
any of them able to tell the difference.

So `provenance.kind` is derived from the instrument's own identity rather than
asserted by the caller; `export_energy_model` refuses a non-measured report; and
the `--allow-synthetic` escape hatch stamps `synthetic — not measured` into the
`source` string that travels with the number forever.

---

## The shape that falls out

```
                    ┌──────────────┐
   volts, amps ---> │  Instrument  │ ---> Sample(t, V, A)
                    └──────────────┘            │
                                                ▼
   one unit of  --> ┌──────────────┐      ┌──────────┐
   work            │   Workload    │ ---> │ Session  │ idle baseline
                    └──────────────┘      └──────────┘ windowed load
                                                │       timed invocations
                        ┌───────────────────────┼───────────────────┐
                        ▼                       ▼                   ▼
                  ┌──────────┐          ┌──────────────┐     ┌────────────┐
                  │ metrics  │          │   thermal    │     │  latency   │
                  │ integral │          │ windows,     │     │ percentiles│
                  │ + error  │          │ throttle     │     │            │
                  └──────────┘          └──────────────┘     └────────────┘
                        └───────────────────────┼───────────────────┘
                                                ▼
                                        ┌──────────────┐
                                        │    Report    │  digest over
                                        │  provenance  │  canonical form
                                        └──────────────┘
                                                │
                                                ▼
                                        ┌──────────────┐
                                        │ energy_model │  refuses synthetic
                                        │   export     │  carries the sentence
                                        └──────────────┘
```

Every arrow is one-way. Nothing downstream can reach back and change how a
sample was taken, and nothing upstream knows what the figures will be used for.

## Decisions with their own files

| Decision | Where |
|---|---|
| The core is instrument-agnostic | [ADR 0001](adr/0001-instrument-agnostic-core.md) |
| Synthetic runs are labelled and refused downstream | [ADR 0002](adr/0002-synthetic-runs-are-labelled.md) |
| Two samplers, and the report says which | [ADR 0003](adr/0003-two-sampling-strategies.md) |

## What was considered and rejected

**A plugin registry for instruments.** Entry points, discovery, a config file
naming a driver. Rejected: the population of instruments in one lab is three,
and a registry adds a way for the report to name a driver that is not the one
that ran.

**Storing raw sample series in the report.** Rejected: report size would scale
with run length rather than window count, and a six-hour soak would produce an
artefact nobody opens. The bench keeps its own series; the report is the
publishable summary.

**A composite efficiency score.** Rejected outright. A single number combining
energy, latency and throughput encodes a weighting that belongs to the reader's
application, and hides the throttle behaviour that motivated the project.

**Auto-detecting the device under test.** Rejected: it would make the harness
know about boards, which is the thing that turns an instrument back into a lab
benchmark script.
