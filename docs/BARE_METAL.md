# Running on bare metal

No container, no orchestrator, no cloud. A Linux machine, an instrument on a
bus, and a device under test drawing current through a shunt.

Everything before this point runs on any laptop with Python. This page is about
the day the meter arrives.

---

## 1. The wiring, before any software

**High-side, always.** The shunt goes between the supply and the device under
test, not between the device and ground. Low-side wiring puts the device's
ground reference above the instrument's, and every reading acquires an offset
that looks exactly like a real difference between two boards.

```
   PSU +5V ──┬── [ shunt 0.1 Ω ] ──┬── DUT V+
             │                     │
          IN+ └─── INA219 ────┘ IN-
                     │
                  I²C ── SDA/SCL/GND ── host
   PSU GND ─────────────────────────── DUT GND ── host GND
```

Three things to check before trusting a single number:

1. **Common ground.** Host, instrument and device under test share one ground.
   Two grounds at different potentials produce readings that drift with load.
2. **Shunt rating.** 0.1 Ω at ±320 mV full scale reaches 3.2 A. Check the
   inrush of your device, not its steady draw — a board that settles at 400 mA
   can pull two amps for a few milliseconds at power-on.
3. **Wire gauge on the supply side.** A thin lead is itself a shunt. If the rail
   sags more than a few tens of millivolts under load, the `volts` column will
   show it, which is the point of recording volts and amps separately.

## 2. Bus access without root

On Debian and derivatives:

```bash
sudo apt install -y i2c-tools python3-venv
sudo raspi-config nonint do_i2c 0        # Raspberry Pi only
sudo usermod -aG i2c "$USER"             # log out and back in
i2cdetect -y 1                           # the instrument should appear, e.g. 0x40
```

If `i2cdetect` shows nothing, stop. No software here can help; it is wiring,
address conflict, or a bus that is not enabled.

**Do not run the harness as root** to work around a permissions problem. A
process that can write anywhere is a process that can overwrite the report it
just wrote.

## 3. Install

```bash
python3 -m venv ~/.venvs/mh
~/.venvs/mh/bin/pip install -e ".[dev,ina219]"
~/.venvs/mh/bin/mh --version
```

The `ina219` extra pulls the bus library. Analysing a report needs neither.

## 4. Quiet the machine

Sustained-load measurement is measurement of the whole machine, not of your
workload. Before a run that anybody will quote:

```bash
sudo systemctl stop unattended-upgrades packagekit          # no background installs
sudo systemctl stop bluetooth avahi-daemon                  # unless under test
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor   # record it, do not change it
```

Record the governor rather than forcing `performance`. A figure taken under a
governor nobody runs in production is a figure about a machine that does not
exist. Put it in `--ambient` and the conditions dict:

```bash
mh run --device uno-q --instrument ina219 \
       --idle-s 30 --windows 10 --window-s 60 \
       --ambient 22.5 --out ./run/uno-q-$(date +%Y%m%d-%H%M).json
```

## 5. Thermals

Ambient temperature is the variable most likely to make two runs disagree, and
it is the one least often recorded. Measure the room, not the case, and take it
at the start of the run.

Where the device can report its own temperature, wire it in:

```python
def thermometer() -> float:
    return int(open("/sys/class/thermal/thermal_zone0/temp").read()) / 1000.0

spec = SessionSpec(device="uno-q", thermometer=thermometer, ...)
```

Without it, the throttle verdict says throughput regressed and refuses to name
a cause. With it, the report carries the rise alongside, and a reader can draw
the conclusion the data supports.

## 6. Running unattended

A ten-window run at sixty seconds is eleven minutes with the baseline. Over SSH,
that is eleven minutes of a connection that might drop.

```bash
systemd-run --user --unit=mh-run --working-directory="$PWD" \
  ~/.venvs/mh/bin/mh run --device uno-q --instrument ina219 \
  --windows 10 --window-s 60 --idle-s 30 --out ./run/report.json

journalctl --user -u mh-run -f
```

`systemd-run` rather than `nohup`: the unit's exit status is recorded, so a run
that died at window seven is distinguishable from one that finished.

## 7. After the run

```bash
mh verify ./run/report.json        # recompute the digest
mh show   ./run/report.json        # read the summary
mh energy-model ./run/report.json --action inference
```

The export refuses if anything about the run was synthetic. On a real
instrument it will not be, and the `source` string it prints is what travels
downstream — carry it verbatim, digest included.

## 8. Calibrate before you publish

The harness cannot audit its own instrument (residual risk R-1 in
[THREAT_MODEL.md](THREAT_MODEL.md)). Once, on a known load:

1. Put a precision resistor across the supply in place of the device.
2. Compute the expected current from the rail voltage and the resistance.
3. Run a short session and compare.
4. Record both figures in the run's `conditions`, and in the build log.

A meter that reads 3 % low is invisible in every report it produces, and shows
up immediately against a known load.

## 9. What still will not be true

- **Inrush is invisible** at roughly 100 Hz. Do not quote peak draw from these
  samples as if it were a peak.
- **Model load is excluded** from both baseline and load window. It is a real
  cost and this harness does not yet characterise it.
- **The mains side is not the DC side.** A smart plug measures the supply's
  losses too, and the identity block is where that has to be said.
