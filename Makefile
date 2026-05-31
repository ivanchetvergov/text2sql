COMPOSE=docker compose --env-file .env -f infra/docker-compose.yml
SERVICE=db

ifneq (,$(wildcard ./.env))
include .env
export
endif

.PHONY: up down logs ps rebuild reset purge psql clean-volume cli clean-logs ckean-logs

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f $(SERVICE)

ps:
	$(COMPOSE) ps

rebuild:
	$(COMPOSE) up -d --build --force-recreate

reset:
	$(COMPOSE) down -v --remove-orphans
	$(COMPOSE) up -d --build

clean-volume:
	$(COMPOSE) down -v --remove-orphans

purge: clean-volume
	@echo "Database volume and container removed. Ready for clean rebuild."

seed:
	@echo "Seeding all entities..."
	python3 seed/seed_runner.py
	@echo "Database seeded successfully!"

psql:
	$(COMPOSE) exec $(SERVICE) psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

cli:
	python3 main.py

clean-logs:
	$(MAKE) -C llm clean-logs

ckean-logs: clean-logs
