.PHONY: up down migrate fmt tf-fmt tf-org-init tf-org-plan tf-dev-init tf-dev-plan health

up:
	docker compose up -d postgres

down:
	docker compose down

migrate:
	@for file in $$(ls migrations/*.sql | sort); do \
		echo "Applying $$file"; \
		docker compose exec -T postgres psql -U finance -d finance < $$file; \
	done

fmt:
	cd worker && python -m ruff format app tests

tf-fmt:
	terraform fmt -recursive infra

tf-org-init:
	terraform -chdir=infra/organization init

tf-org-plan:
	terraform -chdir=infra/organization plan

tf-dev-init:
	terraform -chdir=infra/environments/dev init

tf-dev-plan:
	terraform -chdir=infra/environments/dev plan

health:
	cd worker && python -m app.cli health
