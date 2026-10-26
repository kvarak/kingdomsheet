COMPOSE ?= docker compose

.PHONY: serve stop check migrate logs

serve: .env
	$(COMPOSE) up -d --build --wait

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
