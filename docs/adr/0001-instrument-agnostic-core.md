# ADR 0001, The core never learns what it is talking to

**Status:** accepted · 2026-08-21

## Context

The obvious first implementation reads an INA219 over I²C, because that is what
is on the bench. Every subsequent instrument then arrives as a special case, and
within three of them the analysis code is full of branches on which meter
produced the samples.

## Decision

The core depends on `Instrument` (`identity` / `open` / `read` / `close`) and
on nothing else. Shunt monitors, bench supplies over SCPI, USB-C inline
analysers, smart plugs and synthetic generators are all the same shape. Backends
live behind optional extras so that analysing somebody else's report never
requires an I²C stack.

## Cost

The interface cannot express what some instruments do well. A supply that
reports its own energy accumulator has that figure discarded in favour of
integrating volts and amps; a meter with hardware triggering cannot expose it.
Both are real losses, accepted in exchange for one analysis path rather than one
per meter.

## Consequence

Anything device-specific lives in a driver and surfaces in `identity().settings`,
where it is recorded in the report and can be argued with.
