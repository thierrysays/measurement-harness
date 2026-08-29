.PHONY: test smoke unit functional security pentest demo lint types sast audit cover counts qa clean docs

# ------------------------------------------------------------------ the tiers
# Each answers a different question. See docs/TEST_STRATEGY.md.

test:
	python -m pytest

smoke:
	python -m pytest -m smoke

unit:
	python -m pytest -m unit

functional:
	python -m pytest -m functional

security:
	python -m pytest -m security

pentest:
	python -m pytest -m pentest

# ------------------------------------------------------------------- the demo
# A six-minute soak in simulated time. The seed is fixed so the run exercises
# the throttle path; do not change it to make an output look better.

demo:
	python -m measurement_harness.cli run \
		--device demo-board --windows 6 --window-s 60 --idle-s 10 \
		--latency-ms 20 --slowdown 18 --droop 8 --seed 12 \
		--out ./run/report.json
	python -m measurement_harness.cli verify ./run/report.json
	@echo
	@echo "and now the part that refuses:"
	-python -m measurement_harness.cli energy-model ./run/report.json

# ------------------------------------------------------------------- the gate
# `make qa` is what CI runs. Everything in it fails the build; nothing prints a
# warning and continues, because a warning nobody must act on is unread.

lint:
	python -m ruff check src tests scripts

types:
	python -m mypy

sast:
	python -m bandit -q -r src

audit:
	python -m pip_audit --progress-spinner off

# A count written next to a command is stale the moment somebody adds a test.
# This is the only part of the gate that reads the documentation.
counts:
	python scripts/check_documented_counts.py

cover:
	python -m pytest --cov=measurement_harness --cov-report=term-missing --cov-fail-under=90

qa: lint types sast audit counts cover

clean:
	rm -rf run .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -name __pycache__ -type d -exec rm -rf {} +
