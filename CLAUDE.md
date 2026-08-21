# measurement-harness — project instructions

A harness that measures power, latency and thermal behaviour under sustained
load, on any device, through any instrument. The product of this repository is
**figures with provenance and error bars**, not benchmarks.

## Commands

```bash
pip install -e ".[dev]"
make test          # 111 tests across five tiers, ~5s
make smoke         # 5 tests, ~1s — run this first on a new machine
make demo          # a synthetic six-minute soak, in simulated time
make qa            # ruff, strict mypy, bandit, pip-audit, coverage >= 90%
python -m pytest tests/unit/test_thermal.py -k noise    # single test
python -m pytest -m pentest                             # one tier
```

## Where things are

| Path | Role |
|---|---|
| `canonical.py` | The only place a report is serialised for hashing. Sorted keys, no NaN. |
| `clock.py` | Injectable time. `ManualClock` is what makes a soak test run in a unit suite. |
| `errors.py` | One exception per failure mode, each with a stable `code`. |
| `instruments/base.py` | The three-method contract. The core knows nothing else. |
| `instruments/synthetic.py` | Deterministic averaging source. Labelled synthetic, always. |
| `instruments/ina219.py` | Declared from the datasheet, refuses to invent readings. |
| `workload.py` | Prepare / invoke / teardown. Opaque to the harness by design. |
| `session.py` | Idle baseline, windowed load, two sampling strategies. |
| `metrics.py` | Trapezoidal integration, nearest-rank percentiles, uncertainty. |
| `thermal.py` | The throttle detector and its anti-noise rule. |
| `report.py` | The artefact and its digest. |
| `energy_model.py` | Export downstream, and refuse to launder a rehearsal as a measurement. |
| `tests/smoke/` | Does it start at all. Subprocess-level, one second. |
| `tests/unit/` | One behaviour of one module, at its boundary. |
| `tests/functional/` | One test per requirement in the functional spec. |
| `tests/security/` | Input the harness did not produce; disclosure; no `eval`. |
| `tests/pentest/` | Attacks on the claim, including two that succeed. |
| `docs/GETTING_STARTED.md` | Neophyte path: no terminal experience assumed. |
| `docs/FUNCTIONAL_SPEC.md` | Actors, FR-1…FR-10, acceptance criteria. |
| `docs/TECHNICAL_REFERENCE.md` | Module by module, every artefact field. |
| `docs/ARCHITECTURE.md` | Why it is shaped this way; what was rejected. |
| `docs/METHOD.md` | What a run does, in order, and why. |
| `docs/REPORT_FORMAT.md` | Every field of every artefact. |
| `docs/BARE_METAL.md` | Real meter, real board: wiring, permissions, calibration. |
| `docs/THREAT_MODEL.md` | Adversaries P1–P3, residual risks R-1…R-5. |
| `docs/CLAIM_MAP.md` | Claim → implementation → the test that proves it. |
| `docs/TEST_STRATEGY.md` | The five tiers and what each is for. |

## Invariants — do not break these without an ADR

1. **A synthetic run never leaves labelled as measured.** `provenance.kind` comes
   from the instrument, not the caller. `export_energy_model` refuses unless
   `allow_synthetic=True`, and then says so permanently in `source`.
2. **The core never learns what instrument it is driving.** Anything
   device-specific lives in a driver and surfaces in `identity().settings`.
3. **A driver that has not run against hardware refuses to read.** Subclass
   `UnportedInstrument`; do not return plausible numbers.
4. **Energy is integrated over actual timestamps**, never mean watts × duration.
5. **Every figure carries an error bar** derived from the instrument's own
   declarations. An instrument declaring nothing gets zero, which is honest.
6. **The throttle verdict never claims a cause.** It says throughput regressed.
7. **`Report.verify()` shares no state with the writer.** Keep it that way.
8. **`measurement-harness/report/v1` is inside the hashed body.** Changing the
   string invalidates every report. Breaking changes get `/v2`.
9. **No runtime dependencies.** The bench machine is always the awkward one.

## The delivery standard

Every deliverable in this repository ships with all of the following. This is the
standing default, not a per-task decision — a change that adds behaviour without
its documentation and its tiers is unfinished, not fast.

1. **Technical documentation** — module by module, every artefact field.
2. **Functional documentation** — actors, numbered requirements, acceptance
   criteria, written so someone who never reads the source can check a claim.
3. **A neophyte path** — a guide assuming no terminal, no Python, no git.
4. **A bare-metal run** — how it works on real hardware with no container.
5. **A full test harness** — smoke, unit, functional, security and pen-test
   tiers, each selectable, each with a stated purpose.
6. **A QA gate** — lint, strict types, SAST, dependency advisories, coverage.
   Everything in it fails the build.
7. **A threat model with residual risks**, each pinned by a test that
   demonstrates the gap rather than hiding it.

## Repository metadata

**Every repository carries `glossolalie-advisory` as a topic.** It is the common
tag across the whole portfolio — the one that makes the family findable from a
single search — and it sits alongside the repository's own descriptive topics
rather than replacing them. A new repository is not finished until it has it.

The rest of the topic list describes *this* repository: what it does, what it
runs on, what standard it answers to. Aim for ten to twenty, lower-case and
hyphenated, and prefer terms somebody would actually search for over terms that
merely sound thorough.

The description is one sentence saying what the thing refuses or measures, not
what category it belongs to.

## Conventions

**Tests assert on the figures, not the log.** Constant power for one second
integrates to exactly that many joules; a single slow window is not a throttle.

**Write the negative test first.** Refusals, insufficient samples, backwards
timestamps, edited reports.

**A pen-test that only passes is a pen-test written afterwards.** Where an attack
succeeds, the test says so and names the residual risk. Two currently do.

**The tier is the directory.** `tests/<tier>/` gets the marker automatically at
collection. Do not add `pytestmark` by hand.

**Docstrings carry the argument, not the mechanics.** Why a control exists and
what it costs. Keep the register.

## Traps

- `InlineSampler` is blind to peak draw during a unit of work. That is
  structural, documented, and the reason `ThreadedSampler` exists. Do not
  "fix" it by having the session poll mid-invocation on real hardware — it
  cannot.
- `SyntheticInstrument` models an *averaging* meter: each reading is the mean
  since the previous one. Removing that makes the inline sampler read pure idle
  and the synthetic demo becomes meaningless.
- The demo seed is fixed so the run exercises the throttle path.
- Nearest-rank percentiles are deliberate: every quoted latency occurred.

## The next milestone

1. Port `ina219.py` against the part. The porting note in the module is the
   specification; the calibration register value must reach `settings`.
2. Replace one estimate downstream with a measured figure and record the gap.
3. Characterise model load and warm-up as their own phase — currently excluded
   from both baseline and load window, and not measured at all.
