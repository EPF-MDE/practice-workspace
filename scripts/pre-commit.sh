#!/bin/sh
. "$(dirname "$0")/check-steps.sh"
require_installed node_modules frontend/node_modules

logs=$(mktemp -d)
trap 'rm -rf "$logs"' EXIT

run() {
  name=$1
  shift
  ("$@" >"$logs/$name.log" 2>&1 || touch "$logs/$name.failed") &
}

run lint-staged npx lint-staged --no-stash --no-hide-partially-staged
run sandcastle-types sandcastle_types
run backend-types backend_types
run backend-boundaries backend_boundaries
run backend-cycles backend_cycles
run frontend-types frontend_types
run frontend-boundaries frontend_boundaries
wait

status=0
for failed in "$logs"/*.failed; do
  [ -e "$failed" ] || continue
  name=$(basename "$failed" .failed)
  echo "✖ $name failed:"
  cat "$logs/$name.log"
  echo
  status=1
done
exit $status
