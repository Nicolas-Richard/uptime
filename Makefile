PORT_OFFSET ?= 0
DJANGO_PORT ?= $(shell echo $$((8000 + $(PORT_OFFSET))))
DYNAMODB_LOCAL_PORT ?= $(shell echo $$((8001 + $(PORT_OFFSET))))
DYNAMODB_ENDPOINT_URL ?= http://localhost:$(DYNAMODB_LOCAL_PORT)
AWS_REGION ?= us-east-1
AWS_ACCESS_KEY_ID ?= local
AWS_SECRET_ACCESS_KEY ?= local

ROOT_DIR := $(shell pwd)
PYTHON ?= $(ROOT_DIR)/.venv/bin/python

export PORT_OFFSET DJANGO_PORT DYNAMODB_LOCAL_PORT DYNAMODB_ENDPOINT_URL AWS_REGION AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY

.PHONY: dev-stack stop run-django run-runner create-tables migrate seed test

dev-stack:
	./scripts/dev-stack.sh

stop:
	docker compose -f compose.yml down
	-pkill -f "manage.py runserver" 2>/dev/null || true

run-django:
	cd src && DJANGO_SETTINGS_MODULE=uptime.settings $(PYTHON) manage.py runserver 0.0.0.0:$(DJANGO_PORT)

run-runner:
	$(PYTHON) scripts/run_checks_local.py

create-tables:
	$(PYTHON) scripts/create_local_tables.py

migrate:
	cd src && DJANGO_SETTINGS_MODULE=uptime.settings $(PYTHON) manage.py migrate

seed:
	$(PYTHON) scripts/seed_demo.py

test:
	DJANGO_SETTINGS_MODULE=uptime.settings PYTHONPATH=$(ROOT_DIR)/src:$(ROOT_DIR) $(PYTHON) -m pytest tests/ src/ --tb=short -v
