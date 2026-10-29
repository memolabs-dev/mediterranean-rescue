.PHONY: help dev seed stop logs test check hooks lint

MANAGE = docker compose run --rm api uv run --no-sync python backend/manage.py
WEB = docker compose run --rm --no-deps web sh -c
# Same Ruff version as uv.lock, so `make lint` needs Docker only.
RUFF = docker run --rm -v "$(CURDIR)":/src -w /src ghcr.io/astral-sh/ruff:0.17.1

# List the commands.
help:
	@awk '/^# /{doc=substr($$0,3)} /^[a-z]+:/{if(doc){split($$0,t,":"); printf "  make %-6s %s\n", t[1], doc}; doc=""}' Makefile

# Start everything with fictional data: http://127.0.0.1:5173, team space on /workspace.
dev:
	python3 scripts/init_local.py
	docker compose build
	docker compose up -d db
	$(MANAGE) migrate --noinput
	@$(MAKE) --no-print-directory seed
	docker compose up -d api web
	@echo ""
	@echo "Ready in a few seconds: http://127.0.0.1:5173 (team space: http://127.0.0.1:5173/workspace)"
	@echo "Follow the logs with 'make logs', stop with 'make stop'."

# Load the fictional events and the local volunteer account (training mode only).
seed:
	@if grep -q '^DATA_MODE=training' .env; then \
		$(MANAGE) seed_kickoff_demo --confirm-local-training && \
		$(MANAGE) setup_local_team --confirm-local-training; \
	else \
		echo "DATA_MODE is not training in .env: no fictional data loaded."; \
	fi

# Stop the containers; the database is kept.
stop:
	docker compose stop

# Follow the API and frontend logs.
logs:
	docker compose logs -f api web

# Run the backend and frontend tests.
test:
	$(MANAGE) test catalog.tests --noinput
	$(WEB) "pnpm install --frozen-lockfile && pnpm test"

# Everything CI checks before a pull request, except the browser tests.
check: lint test
	$(MANAGE) makemigrations --check --dry-run
	$(WEB) "pnpm install --frozen-lockfile && pnpm lint && pnpm typecheck && pnpm build"

# Check Python style, like the lint job in GitHub Actions.
lint:
	$(RUFF) check backend scripts
	$(RUFF) format --check backend scripts

# Install the pre-commit hook for this checkout (once after cloning).
hooks:
	sh scripts/install-git-hooks.sh
