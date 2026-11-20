#!/bin/sh
# The fast part of `npm run check`, every job in parallel, in a few seconds.
# Tests stay in `npm run check`. The shape is the Software Factories cohort's
# (https://github.com/ai-hero-dev/cohort-005-project, scripts/pre-commit.sh),
# with the back end's jobs added beside the front end's. The commands it shares
# with check are in check-steps.sh.
# lint-staged runs with --no-stash: its checks never write, and stashing would
# change the working tree under the checks running beside it.

. "$(dirname "$0")/check-steps.sh"

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
