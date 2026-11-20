#!/bin/sh
# Everything, in one command: what an implementing agent, the review run, CI
# and the Instructor all call green. The pre-commit hook runs its fast part.
#
# Usage: npm run check [-- part ...], a part being one of $parts below.
# With no part, every part runs.
set -e

parts="repository backend frontend"

step() { printf '\n▶ %s\n' "$1"; }

repository() {
  step "Repository: file size (every tracked file)"
  git ls-files -z | xargs -0 node scripts/check-file-tokens.js
  step "Repository: format (Markdown, JSON, configuration)"
  npx biome format .
  npx prettier --check "**/*.md"
  step "Repository: lint (everything outside the front end)"
  npx oxlint -c .oxlintrc.json --ignore-pattern "frontend/**"
}

backend() (
  cd backend
  step "Back end: format and lint"
  uv run --frozen ruff format --check .
  uv run --frozen ruff check .
  step "Back end: types"
  uv run --frozen mypy
  step "Back end: boundaries"
  uv run --frozen tach check
  uv run --frozen python scripts/check_cycles.py
  step "Back end: tests"
  uv run --frozen pytest
)

frontend() {
  step "Front end: lint"
  npx oxlint -c .oxlintrc.json frontend
  step "Front end: types"
  npm --prefix frontend run --silent typecheck
  step "Front end: boundaries"
  npm --prefix frontend run --silent lint:boundaries
}

[ $# -gt 0 ] || set -- $parts
for part in "$@"; do
  case $part in
    repository | backend | frontend) "$part" ;;
    *) echo "Unknown part: $part (one of: $parts)" >&2; exit 2 ;;
  esac
done

printf '\n✔ check passed: %s\n' "$*"
