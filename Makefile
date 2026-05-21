.PHONY: dev migrate logs stop build

dev:
	docker compose up db cache -d
	uv run --env-file .env uvicorn app.main:app --reload

migrate:
	uv run --env-file .env alembic upgrade head

logs:
	docker compose logs -f db cache

stop:
	docker compose down

build:
	docker compose up --build
