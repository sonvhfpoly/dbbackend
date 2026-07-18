.DEFAULT_GOAL := help

APP_DIR := app
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: help install start dev test migrate migrate-down migrate-current docker-build docker-run

help: ## Hiển thị các lệnh có sẵn
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Cài dependencies bằng uv
	uv sync

start: ## Chạy API ở chế độ development (reload, http://127.0.0.1:8000)
	cd $(APP_DIR) && uv run --project .. uvicorn main:app --reload --host $(HOST) --port $(PORT)

dev: start ## Alias của start

test: ## Chạy unit tests
	uv run pytest -q

migrate: ## Áp dụng Alembic migrations mới nhất
	cd $(APP_DIR) && uv run --project .. alembic upgrade head

migrate-down: ## Roll back một Alembic migration
	cd $(APP_DIR) && uv run --project .. alembic downgrade -1

migrate-current: ## Xem Alembic revision hiện tại
	cd $(APP_DIR) && uv run --project .. alembic current

docker-build: ## Build Docker image (IMAGE có thể override)
	docker build -t $(IMAGE) .

docker-run: ## Chạy Docker image tại http://127.0.0.1:8080 (cần DATABASE_URL)
	docker run --rm -p 8080:8080 -e DATABASE_URL="$(DATABASE_URL)" $(IMAGE)

IMAGE ?= career-guidance
