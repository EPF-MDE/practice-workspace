#!/bin/sh
# Everything, in one command: what an implementing agent, the review run, CI
# and the Instructor all call green. The pre-commit hook runs its fast part.
set -e

step() { printf '\n▶ %s\n' "$1"; }

step "File size (every tracked file)"
git ls-files -z | xargs -0 node scripts/check-file-tokens.js

step "Format"
npx biome format .
npx prettier --check "**/*.md"
(cd backend && uv run --frozen ruff format --check .)

step "Lint"
npx oxlint -c .oxlintrc.json
(cd backend && uv run --frozen ruff check .)

step "Types"
(cd backend && uv run --frozen mypy)
npm --prefix frontend run --silent typecheck

step "Boundaries"
(cd backend && uv run --frozen tach check)
(cd backend && uv run --frozen python scripts/check_cycles.py)
npm --prefix frontend run --silent lint:boundaries

step "Tests"
(cd backend && uv run --frozen pytest)

printf '\n✔ check passed\n'
