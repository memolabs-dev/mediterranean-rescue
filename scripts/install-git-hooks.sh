#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
[ -e .git ] || { echo "Not a Git checkout"; exit 1; }
current="$(git config --local --get core.hooksPath || true)"
if [ -n "$current" ]; then
  echo "Preserving existing core.hooksPath=$current; install pre-commit there manually if required."
  exit 0
fi
if command -v uvx >/dev/null 2>&1; then
  uvx pre-commit install --install-hooks
elif python3 -c 'import pre_commit' >/dev/null 2>&1; then
  python3 -m pre_commit install --install-hooks
else
  echo "Missing pre-commit tool; install uv (uvx) or Python pre-commit, then run make hooks" >&2
  exit 1
fi
