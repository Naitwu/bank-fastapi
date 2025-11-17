build:
	docker compose -f local.yml up --build -d --remove-orphans

up:
	docker compose -f local.yml up -d

down-v:
	docker compose -f local.yml down -v

down:
	docker compose -f local.yml down

bank-config:
	docker compose -f local.yml config

makemigrations:
	docker compose -f local.yml exec -it api alembic revision --autogenerate -m "$(name)"

migrate:
	docker compose -f local.yml exec -it api alembic upgrade head

history:
	docker compose -f local.yml exec -it api alembic history

current-migration:
	docker compose -f local.yml exec -it api alembic current

downgrade:
	docker compose -f local.yml exec -it api alembic downgrade "$(revision)"

inspect-network:
	docker network inspect bank_local_nw

psql:
	docker compose -f local.yml exec -it postgres psql -U bankfastapiuser -d bankfastapidb
logs:
	docker compose -f local.yml logs -f api