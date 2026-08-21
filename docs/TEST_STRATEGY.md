# Test strategy

Five tiers, each answering a different question. The tier a test belongs to is
the directory it lives in — the marker is applied from the path at collection
time, so a test cannot be moved between tiers and keep an old label.

```
make smoke        # does it start at all                     ~1 s
make unit         # does each part behave at its boundary    ~3 s
make functional   # does it meet the specification           ~4 s
make security     # what does it do with input it distrusts  ~1 s
make pentest      # can the claim be broken                  ~2 s
make test         # all of the above
make qa           # lint, strict types, SAST, advisories, coverage
```

---

## `tests/smoke/` — does it start

Runs after an install on a machine nobody has used before. Imports the package,
runs the CLI as a **subprocess**, produces one small report and parses it. Under
a second, no cleverness.

If these fail, nothing below is worth reading. They exist because a tool that
works only when imported by its own test suite is a tool nobody can run.

## `tests/unit/` — one behaviour, at its boundary

Constant power for exactly one second integrates to exactly that many joules. A
single slow window is not a throttle. A reading taken before `open()` raises
rather than returning zero. Fast, deterministic, no subprocesses.

The house rule: **assert on the figures, not on the log.** A test that checks
something was logged is testing the logger.

## `tests/functional/` — does it meet the specification

One test per requirement in [FUNCTIONAL_SPEC.md](FUNCTIONAL_SPEC.md), named for
the requirement it discharges (`test_fr5_...`). Written from the specification
rather than from the code, and run through the CLI as a real process wherever the
requirement is about an artefact leaving the machine.

Deleting a requirement deletes its test. Adding one adds both.

## `tests/security/` — input the harness did not produce

A report is a file that arrives from somewhere: an older version, a different
implementation, a colleague's text editor, or somebody who wants a number
believed. The property under test is that **untrusted input can make the harness
refuse, and cannot make it do anything else** — no execution, no traversal, no
unbounded allocation, no silent acceptance.

Includes a source-level check that the package contains no `eval`, `exec`,
`pickle`, `marshal` or `subprocess` call. A report is data; the moment a loader
can be persuaded to execute part of its input, every other control is
decorative.

Also includes disclosure checks: no environment variables, no home directories,
and no raw sample series in an artefact that is meant to be publishable.

## `tests/pentest/` — attacks on the claim

Not exercises of the code. Each test takes the position of an adversary from
[THREAT_MODEL.md](THREAT_MODEL.md) — a motivated author (P1), a hostile
instrument or workload (P2) — and tries to make the harness produce a figure
that is wrong and believed.

**Where an attack succeeds, the test says so and is named as a limitation.**
`test_a_fully_recomputed_forgery_is_undetectable_from_the_file_alone` and
`test_an_instrument_that_understates_current_is_believed` both pass by
demonstrating a gap. A pen-test suite containing only attacks the system
survives is a suite written after the fact.

## `make qa` — the gate

| Step | Tool | Fails on |
|---|---|---|
| Lint | `ruff` | any finding; `E`, `F`, `I`, `UP`, `B`, `SIM` are selected |
| Types | `mypy --strict` | any error, across the whole package |
| SAST | `bandit -r src` | any unjustified finding; suppressions carry a reason inline |
| Advisories | `pip-audit` | any known vulnerability in the resolved environment |
| Coverage | `pytest --cov` | below 90 % |

Everything in the gate fails the build. Nothing prints a warning and continues,
because a warning nobody must act on is a warning nobody reads.

---

## Hardware tests

The `hardware` marker is reserved for tests that need a real instrument. They
are deselected unless `MH_HARDWARE=1` is set, and CI never sets it. When
`ina219.py` is ported, its bench test lands here and the porting note in the
module becomes the specification it is written against.

## What the tiers do not cover

- **Accuracy.** No tier can tell you the instrument is right (R-1).
- **Long-run stability.** Nothing runs for six real hours in CI. The simulated
  clock makes a six-minute soak instant, and a six-hour soak is a bench
  procedure, not a test.
- **Concurrency.** `ThreadedSampler` is exercised on real runs but not raced
  against a hostile scheduler.
