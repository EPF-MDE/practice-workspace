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
  step "Repository: triggers (no workflow_run, pull_request_target runs no code)"
  node scripts/check-workflow-triggers.js .github/workflows/*.yml
  step "Repository: caches (every agent workflow reads a key warm-caches.yml writes)"
  node scripts/check-cache-keys.js .github/workflows/*.yml
  step "Repository: Markdown (no hard-wrapped paragraph or list item)"
  git ls-files -z '*.md' | xargs -0 node scripts/check-markdown-wraps.js
  step "Repository: names (none the glossary retired)"
  git ls-files -z | xargs -0 node scripts/check-retired-names.js
  step "Repository: Store (no stored format in a test outside its contract suite)"
  git ls-files -z 'backend/tests/*.py' | xargs -0 python3 scripts/check-store-format-imports.py
  step "Repository: Store (no entry kind as a literal outside the Store)"
  git ls-files -z 'backend/*.py' | xargs -0 python3 scripts/check-store-kinds.py
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
  step "Back end: the Demo course (verify, as the Engine loads it at start)"
  uv_backend python -m app verify ../demo-course
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
