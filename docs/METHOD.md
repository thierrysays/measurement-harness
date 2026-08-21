# Method

What a run does, in order, and why each part is where it is.

## 1. Idle baseline, before anything else

Ten seconds of sampling with the workload not yet prepared. This produces the
idle floor in watts.

Without it there is no honest per-operation figure. A board drawing 0.6 W doing
nothing and 3.0 W under load spends a fifth of its energy simply being switched
on, and that fifth belongs to the duty cycle of the deployment, not to the
action. Two boards with different idle draw cannot be compared on total energy
per operation at all; they can be compared on energy above idle.

The baseline is taken **before** `prepare()`, so model loading and cache warming
land in neither the baseline nor the measured window. They are their own event
and this harness does not currently characterise them. That is a gap, stated
here rather than discovered later.

## 2. Sustained load, in windows

`windows × window_s` seconds of continuous invocation, sliced into equal
windows. Defaults are six windows of sixty seconds — six minutes, which is long
enough for a passively-cooled SoC to reach a steady state and short enough that
nobody skips the step.

Each window records its operation count, mean power, mean latency and peak
temperature if one is available. Throughput per window is the series the
throttle detector works on.

## 3. Integration, not averaging

Energy is the trapezoidal integral of instantaneous power over the timestamps
the sampler actually achieved. The alternative — mean watts multiplied by
wall-clock duration — is correct only when sampling is uniform, and sampling is
least uniform under exactly the sustained load being characterised.

`max_gap_s` is reported for this reason. A gap far above the nominal sample
interval means the sampler was starved and the integral is interpolating across
a period nobody observed. It is not an error; it is a caveat the reader is
entitled to.

## 4. The throttle rule

Compare the first window's throughput against the mean of the tail. Flag a
regression beyond the threshold. Report the onset only where a window and its
`consecutive` successors all stay below threshold.

The consecutive rule is the whole defence against crying wolf. In a long run
under a general-purpose OS, single windows dip for reasons that have nothing to
do with the device: a log rotation, a network stack waking up, a scheduler
decision. Without the rule, the detector reports thermal throttling every time
something else happens on the machine.

What the verdict deliberately does not say is *why*. Sustained slowdown has
several causes and this harness observes one symptom. Where the device under
test supplies a temperature series, the rise is reported alongside, and a reader
can draw the conclusion the data supports.

## 5. Uncertainty

Two contributions, added:

- **Proportional**: the instrument's rated accuracy as a percentage of reading.
- **Absolute**: the smallest current step the instrument can resolve, times mean
  bus voltage, times duration — the energy that is invisible to it regardless of
  how long you measure.

An instrument that declares neither gets an error bar of zero, which is honest:
the report carries the instrument block, so a reader can see that it declared
nothing rather than that it was perfect.

## 6. What is not measured

- **Cool-down.** It varies with the room more than with the device.
- **Inrush.** Sampling at ~100 Hz cannot see it. Claiming otherwise from these
  samples would be fabrication.
- **Model load and warm-up.** Excluded from both baseline and load window,
  and not currently characterised as their own phase.
- **Anything on the mains side of a DC supply.** Where a smart plug is the
  instrument, the report measures the supply too, and the identity block is
  where that has to be said.
