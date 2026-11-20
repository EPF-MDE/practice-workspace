uv_backend() { (cd backend && uv run --frozen "$@"); }

sandcastle_types() {
  npx tsc -p tsconfig.json --incremental \
    --tsBuildInfoFile node_modules/.cache/sandcastle.tsbuildinfo
}

backend_types() { uv_backend mypy; }
backend_comments() {
  git ls-files -z '*.py' '*.sh' .husky/pre-commit |
    xargs -0 uv run --project backend --frozen python scripts/check-comments.py
}
backend_boundaries() { uv_backend tach check; }
backend_cycles() { uv_backend lint-imports; }

frontend_types() { npm --prefix frontend run --silent typecheck; }
frontend_boundaries() { npm --prefix frontend run --silent lint:boundaries; }

require_installed() {
  missing=""
  for dir in "$@"; do
    [ -d "$dir" ] || missing="$missing $dir"
  done
  [ -z "$missing" ] && return 0
  echo "✖ Missing dependencies:$missing" >&2
  echo "  Run \`npm run setup\` (once per clone and per worktree)." >&2
  exit 1
}
