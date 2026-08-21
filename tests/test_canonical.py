"""Determinism of the bytes under every digest."""

import math

import pytest

from measurement_harness import canonical


def test_key_order_does_not_change_the_digest():
    a = {"volts": 5.0, "amps": 0.4, "nested": {"b": 2, "a": 1}}
    b = {"nested": {"a": 1, "b": 2}, "amps": 0.4, "volts": 5.0}
    assert canonical.digest(a) == canonical.digest(b)


def test_a_changed_value_changes_the_digest():
    a = {"joules": 1.0}
    b = {"joules": 1.0000001}
    assert canonical.digest(a) != canonical.digest(b)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_floats_are_refused_rather_than_serialised(bad):
    with pytest.raises(ValueError):
        canonical.digest({"mean_watts": bad})


def test_non_finite_is_refused_when_buried_in_a_list():
    with pytest.raises(ValueError):
        canonical.digest({"windows": [{"ops": 1}, {"ops": math.nan}]})
