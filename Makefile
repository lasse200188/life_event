SHELL := /bin/bash
VENV := .venv
PYTHON := $(CURDIR)/$(VENV)/bin/python
UV := uv

.PHONY: help setup test test-workflow test-backend lint-backend

help:
	@echo "Targets:"
	@echo "  make setup          - Create/refresh .venv and install backend dev deps via uv"
	@echo "  make test           - Run workflow validation + backend test suites"
	@echo "  make test-workflow  - Run workflow-marked tests only"
	@echo "  make test-backend   - Run backend tests except workflow-marked tests"
	@echo "  make lint-backend   - Run backend lint checks"

setup:
	$(UV) venv --clear $(VENV)
	. $(VENV)/bin/activate && $(UV) pip install -e './backend[dev]'

test: test-workflow test-backend

test-workflow:
	cd backend && $(PYTHON) -m app.tools.validate_all_workflows ../workflows
	cd backend && $(PYTHON) -m pytest -q -m workflow

test-backend:
	cd backend && $(PYTHON) -m pytest -q -m "not workflow"

lint-backend:
	cd backend && $(PYTHON) -m ruff check .
	cd backend && $(PYTHON) -m black --check .
