.PHONY: dev test test-all lint format migrate migration docker-up docker-down seed install

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	APP_ENV=test OPENAI_API_KEY=sk-test python -m pytest tests/unit/ -v

test-all:
	APP_ENV=test OPENAI_API_KEY=sk-test python -m pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	ruff check app/ tests/

format:
	ruff format app/ tests/

migrate:
	alembic upgrade head

migration:
	@read -p "Migration adı: " name; alembic revision --autogenerate -m "$$name"

seed:
	python scripts/seed_curriculum.py

eval-kt:
	python scripts/eval_kt.py

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down -v
