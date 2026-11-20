#!/bin/sh
set -e

parts="repository backend frontend"

. "$(dirname "$0")/check-steps.sh"

step() { printf '\n▶ %s\n' "$1"; }

repository() {
  require_installed node_modules
  step "Repository: file size (every tracked file)"
  git ls-files -z | xargs -0 node scripts/check-file-tokens.js
  step "Repository: secrets (POSTHOG_API_KEY on the agent's step only)"
  node scripts/check-agent-secrets.js .github/workflows/*.yml
  step "Repository: triggers (no pull_request_target, no workflow_run)"
  node scripts/check-workflow-triggers.js .github/workflows/*.yml
  step "Repository: format (Markdown, JSON, configuration)"
  npx biome format .
  step "Repository: lint (everything outside the front end)"
  npx oxlint -c .oxlintrc.json --ignore-pattern "frontend/**"
  step "Repository: types (the Sandcastle scripts in .sandcastle/)"
  sandcastle_types
  step "Repository: tests (the Sandcastle scripts and scripts/)"
  npx vitest run .sandcastle/ scripts/
}

backend() {
  step "Back end: format and lint"
  uv_backend ruff format --check .
  uv_backend ruff check .
  step "Back end: comments (and the shell scripts', against lint-rules/comments-baseline.json)"
  backend_comments
  step "Back end: types"
  backend_types
  step "Back end: boundaries"
  backend_boundaries
  backend_cycles
  step "Back end: the Demo course (check, as the app loads it at start)"
  uv_backend python -m app check ../demo-course
  step "Back end: tests"
  uv_backend pytest
}

frontend() {
  require_installed node_modules frontend/node_modules
  step "Front end: lint"
  npx oxlint -c .oxlintrc.json frontend
  step "Front end: types"
  frontend_types
  step "Front end: boundaries"
  frontend_boundaries
  step "Front end: build"
  npm --prefix frontend run --silent build
  step "Front end: browser tests (the Path on the Demo course, own server and port)"
  npm --prefix frontend run --silent test
}

[ $# -gt 0 ] || set -- $parts
for part in "$@"; do
  case $part in
    repository | backend | frontend) "$part" ;;
    *) echo "Unknown part: $part (one of: $parts)" >&2; exit 2 ;;
  esac
done

printf '\n✔ check passed: %s\n' "$*"
