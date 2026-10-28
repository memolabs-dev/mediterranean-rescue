.PHONY: hooks lint

# Install Git's pre-commit entrypoint for this checkout (once after cloning).
hooks:
	sh scripts/install-git-hooks.sh

# Local counterpart to the Python lint job in GitHub Actions.
lint:
	uv run --frozen ruff check backend scripts
	uv run --frozen ruff format --check backend scripts
