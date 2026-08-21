# Getting started

**From a machine with nothing installed to a measurement you can defend, in
about twenty minutes.**

This guide assumes nothing. If you have never opened a terminal, never installed
Python and have never used git, you are the reader it was written for. Every
command is given in full, and where a step can go wrong the failure and its fix
are written next to it.

You do **not** need any hardware. Nothing in this guide touches an instrument.

If you already work in Python: `pip install -e ".[dev]" && make demo` and skip
to [What the demonstration shows](#what-the-demonstration-shows).

---

## Table of contents

- [Part 0 — What you are about to run, and why](#part-0--what-you-are-about-to-run-and-why)
- [Part 1 — Open a terminal](#part-1--open-a-terminal)
- [Part 2 — Install Python](#part-2--install-python)
- [Part 3 — Get the code](#part-3--get-the-code)
- [Part 4 — Make a virtual environment](#part-4--make-a-virtual-environment)
- [Part 5 — Install the project](#part-5--install-the-project)
- [Part 6 — Run the tests](#part-6--run-the-tests)
- [Part 7 — Run the demonstration](#part-7--run-the-demonstration)
- [What the demonstration shows](#what-the-demonstration-shows)
- [Part 8 — Check the report yourself](#part-8--check-the-report-yourself)
- [Part 9 — Try to cheat](#part-9--try-to-cheat)
- [Part 10 — Look inside the report](#part-10--look-inside-the-report)
- [Part 11 — Measure your own workload](#part-11--measure-your-own-workload)
- [Troubleshooting](#troubleshooting)

---

## Part 0 — What you are about to run, and why

Imagine a small computer running an AI model continuously — inspecting parts on
a conveyor, say. Two questions decide whether it can be deployed: how much power
does it draw, and does it keep up.

Both are usually answered badly. Someone runs the model once, times it, quotes a
wattage from a datasheet, and publishes. The measurement takes six seconds and
the machine is cold throughout.

Run that same machine for six minutes and something else happens. The chip warms
up, hits its temperature limit, and slows itself down to avoid damage. This is
called **thermal throttling**, and it is completely normal. The throughput after
throttling is often twenty or thirty percent below the published figure — and it
is the only figure the deployment ever experiences.

This project measures the second one.

You will run a simulated six-minute test. Nothing real is measured, and the
report says so in a field you cannot miss — which is the other thing this project
is about, and the part you will test yourself in Part 9.

**Time:** about twenty minutes, most of it downloads.
**Cost:** nothing.
**Risk:** none. Everything happens in one folder you can delete afterwards.

---

## Part 1 — Open a terminal

A terminal is a window where you type commands instead of clicking.

**Windows** — press the Windows key, type `powershell`, press Enter.

**macOS** — press ⌘ + Space, type `terminal`, press Enter.

**Linux** — press Ctrl + Alt + T, or find "Terminal" in your applications.

You will see a prompt: some text ending in `>` or `$` or `%`. Commands go after
it. Type them exactly, then press Enter. Nothing happens until you press Enter.

Throughout this guide, lines you type are shown like this:

```bash
some command
```

Do not type the backticks.

---

## Part 2 — Install Python

Python is the language this project is written in. Check whether you have it:

```bash
python3 --version
```

If you see `Python 3.10` or higher, skip to Part 3.

**If you see an error, or a version below 3.10:**

- **Windows** — download from [python.org/downloads](https://www.python.org/downloads/).
  During installation, tick **"Add Python to PATH"**. This matters; if you miss
  it, the terminal will not find Python afterwards. Then close and reopen
  PowerShell.
- **macOS** — download from the same place, or if you have Homebrew:
  `brew install python@3.12`.
- **Linux (Debian/Ubuntu)** — `sudo apt update && sudo apt install -y python3 python3-venv python3-pip`.
  The `python3-venv` part is easy to forget and Part 4 will fail without it.

On Windows, the command is often `python` rather than `python3`. If `python3`
says "not recognised", try `python` everywhere below.

---

## Part 3 — Get the code

You need git. Check:

```bash
git --version
```

If that errors, install it from [git-scm.com/downloads](https://git-scm.com/downloads),
then close and reopen the terminal.

Now download the code:

```bash
git clone https://github.com/thierrysays/measurement-harness.git
cd measurement-harness
```

`cd` means "change directory" — you are now working inside the folder that was
just created. Everything from here happens in that folder.

Check you are in the right place:

```bash
ls
```

You should see `README.md`, `src`, `tests`, `docs`, `pyproject.toml`. On Windows
PowerShell, `ls` works too.

---

## Part 4 — Make a virtual environment

A virtual environment is a private copy of Python for this project. It means
nothing you install here can break anything else on your machine, and deleting
the folder undoes everything.

```bash
python3 -m venv .venv
```

That creates a `.venv` folder. Now **activate** it:

**macOS / Linux:**
```bash
source .venv/bin/activate
```

**Windows PowerShell:**
```bash
.venv\Scripts\Activate.ps1
```

Your prompt should now start with `(.venv)`. That is how you know it worked.

> **If Windows says "running scripts is disabled":** run
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, answer
> `Y`, then try activating again.

**You must activate the environment in every new terminal window.** If a command
later says "command not found", this is almost always why.

---

## Part 5 — Install the project

```bash
pip install -e ".[dev]"
```

This takes a minute or two. The `-e` means "editable" — if you change the code,
the change takes effect immediately. The `[dev]` part adds the testing tools.

Check it worked:

```bash
mh --version
```

You should see `measurement-harness 0.1.0`.

`mh` is the command this project installs. It is short for measurement harness.

---

## Part 6 — Run the tests

Before running anything, prove the code does what it claims:

```bash
make test
```

> **If `make` is not available on Windows**, use `python -m pytest` instead.
> Every `make` command in this guide has a plain equivalent, listed in the
> `Makefile`.

You should see a row of dots and a count. Every one of those is a claim this
project makes about itself, checked.

Try running just the fastest tier:

```bash
make smoke
```

Five tests, about a second. That is the tier you run on a machine you have never
used before, to find out whether anything works at all.

---

## Part 7 — Run the demonstration

```bash
make demo
```

This simulates a six-minute test in about a second, using a simulated clock. It
writes a report to `run/report.json` and prints a summary:

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

---

## What the demonstration shows

Read that output line by line. Each one is there for a reason.

**`instrument : synthetic (synthetic)`** — the word in brackets is the
provenance. It says nothing here was measured. It is derived from the instrument
itself, not typed by whoever ran the test, and you cannot change it without
breaking the report.

**`idle : 0.603 W`** — what the device draws doing nothing. It is measured
separately and subtracted, because otherwise a board that idles high looks
expensive at everything.

**`energy/op : 69.979 mJ above idle`** — the cost of one unit of work, with the
idle floor removed. The `±` is the error bar. Here it is zero because the
synthetic instrument honestly declares no accuracy; a real meter declares its
own, and the figure carries it.

**`latency : p50 28.8 ms, p95 40.1 ms`** — half the operations finished within
28.8 ms; ninety-five percent within 40.1 ms. The average is deliberately not
shown first: an average hides the slow tail, and the slow tail is what people
notice.

**`sustained : THROTTLED from t=60s, 46.0 -> 31.5 ops/s`** — this is the whole
point. The device started at 46 operations per second and settled at 31.5. Any
figure taken in the first minute would have been wrong by a third.

Note what it does *not* say. It says throughput regressed, not "the device
overheated". Slowdown has several possible causes, and this run had no
thermometer, so the report declines to name one.

**`report_id : sha256:...`** — a fingerprint of everything above.

---

## Part 8 — Check the report yourself

The command that produces a report and the command that checks one are separate
on purpose. A tool that verifies its own output has verified nothing an auditor
cares about.

```bash
mh verify run/report.json
```

```
report_id verified: sha256:b8f4b6da…
provenance        : synthetic
```

This recomputed the fingerprint from the file's contents and compared. Anyone
can run it, on any machine, against a report someone sent them.

---

## Part 9 — Try to cheat

This is the interesting part. Open `run/report.json` in any text editor — Notepad
is fine.

Find the line that says `"kind": "synthetic"` and change it to `"measured"`. Save
the file. Now:

```bash
mh verify run/report.json
```

```
report-invalid: digest mismatch: file claims sha256:b8f4b6da…, body hashes to sha256:2c9e01a7…
```

Try something subtler. Undo that change, and instead find
`"joules_per_operation_above_idle"` and halve the number — make the device look
twice as efficient. Verify again. Same result.

Now try the thing the project actually refuses:

```bash
mh energy-model run/report.json
```

```
synthetic-result-refused: report sha256:… has provenance 'synthetic'; pass
allow_synthetic=True to export a rehearsal figure, which will be labelled as one
```

That command exports a figure for another system to use. It will not hand over a
number from a run where nothing was measured. You can insist:

```bash
mh energy-model run/report.json --allow-synthetic
```

and it complies — but look at the `source` field in the output. It says
`synthetic — not measured`, and that sentence travels with the number wherever it
goes.

> **One honest caveat.** If you edit the report *and* recompute the fingerprint,
> the file verifies. The fingerprint detects editing, not authorship — nothing
> here signs reports, because choosing how to manage signing keys belongs to
> whoever runs the bench. This is written down as residual risk R-2 in
> [THREAT_MODEL.md](THREAT_MODEL.md), and there is a test that demonstrates it
> rather than hiding it.

Restore the file when you are done:

```bash
make demo
```

---

## Part 10 — Look inside the report

```bash
mh show run/report.json
```

Or open `run/report.json` in a text editor. It is plain JSON — text with braces.

Things worth finding:

- **`windows`** — one entry per minute of the run. Compare the first
  `throughput_ops_s` with the last; that difference is the throttling.
- **`instrument`** — what took the readings, its rated accuracy, its settings.
- **`load.max_gap_s`** — the longest gap between two readings. If it is far above
  the sampling interval, the machine was too busy to sample properly and the
  energy figure is interpolating across a period nobody observed.
- **`thermal.caveat`** — the sentence saying that regression is observed, not
  attributed.

What you will *not* find: the raw readings. A six-hour run would produce a file
nobody could open, so the report carries summaries. The bench keeps its own
series.

---

## Part 11 — Measure your own workload

The harness does not know or care what the work is. Give it something with three
methods:

```python
# my_workload.py
from measurement_harness.instruments.synthetic import SyntheticInstrument
from measurement_harness.session import Session, SessionSpec

class MyWorkload:
    def name(self): return "my-model"
    def describe(self): return {"model": "resnet18", "input": "224x224"}
    def prepare(self):  ...   # load the model, warm the caches
    def invoke(self):   ...   # ONE inference. The harness times this call.
    def teardown(self): ...   # release what prepare acquired

spec = SessionSpec(device="my-laptop", idle_s=10, windows=6, window_s=60)
result = Session(SyntheticInstrument(), MyWorkload(), spec).run()
print(result.joules_per_operation_above_idle, result.throttle.throttled)
```

Run it with `python my_workload.py`. With a synthetic instrument the energy
figures are fiction — but the **latency and throughput figures are real**,
because those are timed by the harness's own clock around your `invoke()`.

That alone will tell you whether your workload slows down under sustained load,
which is usually the question that matters, and needs no hardware at all.

When you have a real meter, [BARE_METAL.md](BARE_METAL.md) covers the wiring,
the permissions and the calibration.

---

## Troubleshooting

**`command not found: mh`**
The virtual environment is not active. Run the activate command from Part 4. Its
prompt should start with `(.venv)`.

**`command not found: python3`**
On Windows, try `python`. Otherwise Python is not installed or was installed
without "Add to PATH" — reinstall and tick the box.

**`No module named venv`**
On Debian/Ubuntu: `sudo apt install python3-venv`.

**`make: command not found`**
Windows does not ship `make`. Use the underlying commands: `python -m pytest`
for `make test`, and the `mh run …` line from the `Makefile` for `make demo`.

**`error: externally-managed-environment`**
You are installing outside a virtual environment. Do Part 4 first. Do not use
`--break-system-packages`; the name is accurate.

**`Permission denied` when writing the report**
You are in a folder you cannot write to. `cd` somewhere in your home directory
and re-clone.

**The tests fail on a fresh clone**
That is worth reporting. Open an issue with the output of `python --version` and
the full failure. A test suite that fails on a clean machine is a defect in the
project, not in your setup.

**Everything worked but the numbers differ from this guide**
The demo is seeded, so the figures should match exactly. If they do not, the
version has moved on. The shape of the output is what matters: an idle figure, a
per-operation figure with an error bar, percentiles, and a sustained-throughput
verdict.
