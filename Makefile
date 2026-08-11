SHELL := /bin/bash
COMPOSE := podman compose
EXEC := $(COMPOSE) exec -T api

.DEFAULT_GOAL := help
.PHONY: help up down logs shell migrate migrations superuser test lint format check ps clean

help:  ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up:  ## Levanta la pila (api, web, db, redis, minio)
	$(COMPOSE) up -d --build

down:  ## Para la pila
	$(COMPOSE) down

ps:  ## Estado de los servicios
	@$(COMPOSE) ps

logs:  ## Sigue los registros de la API
	$(COMPOSE) logs -f api

shell:  ## Consola de Django
	$(COMPOSE) exec api python manage.py shell

migrations:  ## Genera migraciones
	$(EXEC) python manage.py makemigrations

migrate:  ## Aplica migraciones
	$(EXEC) python manage.py migrate

superuser:  ## Crea un administrador
	$(COMPOSE) exec api python manage.py createsuperuser

test:  ## Ejecuta las pruebas
	$(EXEC) pytest --cov=apps --cov-report=term-missing

lint:  ## Comprueba estilo y formato
	$(EXEC) ruff check .
	$(EXEC) ruff format --check .

format:  ## Aplica formato
	$(EXEC) ruff check --fix .
	$(EXEC) ruff format .

check: lint test  ## Todo lo que exige la CI

clean:  ## Para la pila y borra sus volúmenes
	$(COMPOSE) down -v
