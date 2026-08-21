# measurement-harness — project instructions

A harness that measures power, latency and thermal behaviour under sustained
load, on any device, through any instrument. The product of this repository is
**figures with provenance and error bars**, not benchmarks.

## Commands

```bash
pip install -e ".[dev]"
make test          # 61 tests, well under a second
make demo          # a synthetic six-minute soak, in simulated time
make qa            # ruff, strict mypy, coverage gate
python -m pytest tests/test_thermal.py -k noise    # single test
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
| `docs/METHOD.md` | What a run does, in order, and why. |
| `docs/REPORT_FORMAT.md` | Every field of every artefact. |

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

## Conventions

**Tests assert on the figures, not the log.** Constant power for one second
integrates to exactly that many joules; a single slow window is not a throttle.

**Write the negative test first.** Refusals, insufficient samples, backwards
timestamps, edited reports.

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
