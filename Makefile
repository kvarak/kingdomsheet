COMPOSE ?= docker compose

.PHONY: serve stop check migrate logs

# Ctrl+C stops following the logs. The services keep running until `make stop`.
serve: .env
	$(COMPOSE) up -d --build --wait
	@echo "Running at http://localhost:8000/ - following logs, Ctrl+C to detach."
	$(COMPOSE) logs -f --tail=20

stop: .env
	$(COMPOSE) stop

check: .env
	$(COMPOSE) --profile test run --rm --build test

migrate: .env
	$(COMPOSE) run --rm web python manage.py migrate

logs: .env
	$(COMPOSE) logs -f

.env:
	@echo "Missing .env. Run: cp .env.example .env, then edit it." && exit 1
