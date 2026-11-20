# The commands `npm run check` and the pre-commit hook share, defined once.
# Sourced, not run: check.sh runs them in sequence, pre-commit.sh runs them in
# parallel. Each one runs from the repository's root.

uv_backend() { (cd backend && uv run --frozen "$@"); }

backend_types() { uv_backend mypy; }
backend_boundaries() { uv_backend tach check; }
backend_cycles() { uv_backend lint-imports; }

frontend_types() { npm --prefix frontend run --silent typecheck; }
frontend_boundaries() { npm --prefix frontend run --silent lint:boundaries; }
