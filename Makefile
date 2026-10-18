.PHONY: install test benchmark compile verify-seed coverage web-build check

VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PYTEST ?= $(VENV)/bin/pytest

$(PYTHON):
	python3 -m venv $(VENV)

install: $(PYTHON)
	$(PYTHON) -m pip install -r requirements-ci.txt
	cd apps/web && npm ci

test:
	$(PYTEST) -q

benchmark:
	$(PYTHON) -c 'import asyncio; from services.evaluation.evaluator import SystemEvaluator; print(asyncio.run(SystemEvaluator.evaluate_full_gridlens()).metrics.model_dump_json())'

compile:
	$(PYTHON) -m compileall -q domain services apps

verify-seed:
	$(PYTHON) scripts/verify_seed.py

coverage:
	$(PYTEST) --cov=domain --cov=services --cov-fail-under=80

web-build:
	cd apps/web && npm run build

check: compile verify-seed coverage web-build
