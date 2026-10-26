COMPOSE ?= docker compose

.PHONY: serve stop check migrate logs reset-password

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

# Usage: make reset-password NAME="Alice". Prompts for the new password.
reset-password: .env
	@test -n "$(NAME)" || (echo 'Usage: make reset-password NAME="Alice"' && exit 1)
	$(COMPOSE) exec web python manage.py reset_name_password "$(NAME)"

.env:
	@echo "Missing .env. Run: cp .env.example .env, then edit it." && exit 1
