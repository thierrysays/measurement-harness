# measurement-harness

**Power, latency and thermal behaviour under sustained load, on whatever you point it at.**

Most published edge-AI figures are burst figures. A model is loaded, an
inference is timed, a wattage is quoted, and everything is measured in the first
thirty seconds, while the board is still cold. Deployments are not cold. A
passively-cooled SoC under continuous inference reaches its thermal limit,
the governor pulls the clock back, and the throughput that matters (the one
in minute four) is a number nobody published.

This harness measures that number. It is instrument-agnostic and
device-agnostic: it knows how to open something that reports volts and amps,
how to invoke a unit of work repeatedly, and how to turn the two into an
artefact somebody who was not in the room can read.

```
pip install -e .
mh run --device my-board --windows 6 --window-s 60 --out ./run/report.json
mh verify ./run/report.json
```

```
  device       : demo-board
  instrument   : synthetic (synthetic)
  sampler      : inline
  operations   : 12207
  idle         : 0.603 W
  load         : 2.976 W mean, 3.594 W peak
  energy/op    : 69.979 mJ above idle (± 0.000 mJ)
  latency      : p50 28.8 ms, p95 40.1 ms, p99 41.3 ms
  sustained    : THROTTLED from t=60s, 46.0 -> 31.5 ops/s (-31.5% throughput)
  report_id    : sha256:b8f4b6da…
```

That run is synthetic (no instrument was attached) and the report says so in
a field, not a footnote. Which brings us to the only rule this project actually
enforces.

---

## The one rule

**A figure that was not measured never leaves here labelled as one.**

Every report carries `provenance.kind`, which is `measured` only when a real
instrument was on a real rail. Everything else is `synthetic`, and
`mh energy-model` refuses to export a downstream figure from such a report
unless you ask for it explicitly, at which point the exported `source` string
says `synthetic — not measured` for as long as that figure lives.

This is not ceremony. Estimated energy figures are load-bearing in more systems
than anyone admits: they set battery sizing, they set duty cycles, and in at
least one design they set a runtime budget that stops a machine. An estimate is
a perfectly good input, right up until nothing in the system can tell it apart
from a measurement.

---

## What it measures

| Figure | What it is | Why the usual version is wrong |
|---|---|---|
| **Energy per operation** | Trapezoidal integral of instantaneous power over the actual sample timestamps, minus the idle floor | Mean watts × wall-clock is quietly wrong whenever the sampler stutters; and including idle draw makes two boards incomparable |
| **Latency percentiles** | p50 / p90 / p95 / p99, nearest-rank | A mean hides the tail, and the tail is the behaviour that gets noticed |
| **Sustained throughput** | Windowed ops/s across a long run, first window against the sustained tail | A one-shot benchmark reports the burst, which the deployment never sees again |
| **Throttle onset** | The first window that stays below threshold, with the consecutive-window rule applied | One slow window is a neighbour's microwave, not a thermal limit |
| **Uncertainty** | Rated accuracy of the instrument, plus an absolute floor from its resolution | Without it, two boards get compared across a difference the meter cannot see |

The throttle verdict states that **throughput regressed**, and names temperature
as evidence only when the device under test supplied a temperature series.
Attributing a slowdown to heat when it might be memory pressure, a background
update or a warm power supply is exactly the overreach this field is full of.

---

## Architecture, in one paragraph

An `Instrument` is anything with `open` / `read` / `close` returning volts and
amps. A `Workload` is anything with `prepare` / `invoke` / `teardown` where
`invoke` performs one unit of work. A `Session` runs an idle baseline, then a
windowed sustained load, integrating power and timing every invocation. A
`Report` is the artefact, digested over its canonical form so it can be verified
rather than trusted. Nothing in the core names a board, a vendor, a model
format, or a bus.

```
instruments/base.py   the three-method contract every driver satisfies
instruments/ina219.py declared from the datasheet, refuses to invent readings
instruments/synthetic.py  deterministic source, so the pipeline is testable cold
workload.py           what the device is asked to do, repeatedly
session.py            idle baseline, windows, two sampling strategies
metrics.py            integration and percentiles, with the error bars
thermal.py            the throttle detector and its anti-noise rule
report.py             the artefact and its digest
energy_model.py       export downstream, and refuse to launder a rehearsal
```

Two sampling strategies, because they are not interchangeable. `InlineSampler`
reads between units of work: exactly reproducible, and blind to the peak draw of
the inference itself. `ThreadedSampler` reads on a background thread at a target
rate and catches it. The report records which was used, since their peak figures
are not comparable.

---

## Adding an instrument

Implement three methods and declare an identity:

```python
class MyMeter:
    def identity(self) -> InstrumentIdentity: ...
    def open(self) -> None: ...          # raise InstrumentNotPresent if absent
    def read(self, t_s: float) -> Sample: ...
    def close(self) -> None: ...
```

The identity block is where the rated accuracy, the resolution, the sample rate
and the wiring go. A driver written from a datasheet but never run against the
part should subclass `UnportedInstrument` and raise, as `ina219.py` does, a
hypothesis in the tree is useful, a hypothesis returning plausible numbers is
not.

---

## Feeding a downstream energy model

Systems that carry a per-action energy table can be fed from a report:

```
mh energy-model ./run/report.json --action inference --action divert_part
```

```json
{
  "schema": "measurement-harness/energy-model/v1",
  "basis": "above_idle",
  "values": { "inference": 0.0699, "divert_part": 0.0699 },
  "source": "measured — ina219 on uno-q, 12207 operations, basis above_idle, report sha256:b8f4b6da…, throughput regressed 31.5% under sustained load",
  "uncertainty_j_per_operation": 0.00035,
  "report_id": "sha256:b8f4b6da…"
}
```

The `source` string is meant to be carried verbatim into whatever consumes it.
A consumer that stores the number and drops the sentence has thrown away the
part that says how much to believe it.

---

## Documentation

| For | Read |
|---|---|
| Never used a terminal, want to see it work | [GETTING_STARTED.md](docs/GETTING_STARTED.md), assumes nothing, twenty minutes, no hardware |
| What it does and what counts as working | [FUNCTIONAL_SPEC.md](docs/FUNCTIONAL_SPEC.md), actors, FR-1…FR-10, acceptance criteria |
| Writing code against it | [TECHNICAL_REFERENCE.md](docs/TECHNICAL_REFERENCE.md), module by module, every artefact field |
| Why it is shaped this way | [ARCHITECTURE.md](docs/ARCHITECTURE.md), the argument, and what was rejected |
| The method behind the numbers | [METHOD.md](docs/METHOD.md), run order, integration, the throttle rule |
| The artefact format | [REPORT_FORMAT.md](docs/REPORT_FORMAT.md), `report/v1` and `energy-model/v1` |
| Putting a real meter on a real board | [BARE_METAL.md](docs/BARE_METAL.md), wiring, bus permissions, calibration |
| What is defended and what is not | [THREAT_MODEL.md](docs/THREAT_MODEL.md), adversaries P1–P3, residual risks R-1…R-5 |
| Every claim and the test that proves it | [CLAIM_MAP.md](docs/CLAIM_MAP.md) |
| How the suite is organised | [TEST_STRATEGY.md](docs/TEST_STRATEGY.md), five tiers and the gate |
| Decisions and their cost | [docs/adr/](docs/adr/) |

---

## The test harness

Five tiers, each answering a different question. The tier a test belongs to is
the directory it lives in, and the marker is applied from the path, so a test
cannot be moved between tiers and keep an old label.

```
make smoke        # does it start at all                     5 tests
make unit         # each part at its boundary               54 tests
make functional   # the specification, end to end           22 tests
make security     # input it did not produce                14 tests
make pentest      # attacks on the claim                    16 tests
make test         # all of it                              111 tests
make qa           # ruff, mypy --strict, bandit, pip-audit, coverage >= 90%
```

The pen-test tier includes two tests that pass **by demonstrating a gap**: a
fully recomputed forgery verifies, and an instrument that understates current is
believed. Both are residual risks R-1 and R-2, and a pen-test suite containing
only attacks the system survives is a suite written after the fact.

---

## What this is not

- **Not a governance tool.** It measures; it does not decide whether a workload
  should run, and it enforces no policy. An instrument that also issues verdicts
  is an instrument whose readings and whose judgements share a failure mode.
- **Not a leaderboard.** There is no score, no composite index, and no ranking
  across devices. Two reports are comparable when their instruments, samplers
  and conditions agree, and the report carries all three so a reader can check.
- **Not a model benchmark.** The workload is opaque to the harness by design. If
  you want to know whether your quantisation helped, run it as the workload,
  the harness will not tell you what it was measuring.
- **Not calibrated.** The uncertainty is propagated from what the instrument
  claims about itself. A meter that lies about its accuracy produces an error
  bar that lies by the same amount.

## Licence

Apache-2.0.
