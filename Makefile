.PHONY: install run test test-live lint format check-env

install:
	python -m pip install -e .[dev]

run:
	uvicorn backend.app.main:create_app --factory --reload

test:
	pytest backend/tests/known_answer

test-live:
	pytest backend/tests/live

lint:
	ruff check .
	mypy backend

format:
	ruff format .
	ruff check --fix .

check-env:
	python scripts/check_env.py
