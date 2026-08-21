.PHONY: test demo lint types qa clean

test:
	python -m pytest

demo:
	python -m measurement_harness.cli run \
		--device demo-board --windows 6 --window-s 60 --idle-s 10 \
		--latency-ms 20 --slowdown 18 --droop 8 --seed 12 \
		--out ./run/report.json
	python -m measurement_harness.cli verify ./run/report.json
	python -m measurement_harness.cli energy-model ./run/report.json --allow-synthetic

lint:
	ruff check src tests

types:
	mypy

qa: lint types
	python -m pytest --cov=measurement_harness --cov-report=term-missing --cov-fail-under=90

clean:
	rm -rf run .pytest_cache .mypy_cache .coverage
	find . -name __pycache__ -type d -exec rm -rf {} +
