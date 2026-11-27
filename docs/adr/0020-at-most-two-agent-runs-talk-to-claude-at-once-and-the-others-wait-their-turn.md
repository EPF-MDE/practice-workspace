# At most two agent runs talk to Claude at once, and the others wait their turn

The factory's agent runs all draw on one Claude 5-hour limit. On 26 November, `agent:rebase` on six pull requests at once, and the reviews those rebases started beside implement runs, hit that limit: seven reviews ended with "You've hit your 5-hour limit" and no verdict (#120). Each agent workflow's `concurrency:` group only serialises runs on the same pull request or issue. **So every agent job waits, in a step named "Wait for an agent slot" just before its agent step, until fewer than `AGENT_SLOTS` (2) agent jobs have passed that step and are still running. A run that waits costs runner minutes, not Claude tokens, and no label is lost.**

- **The cap is defined once**, as `AGENT_SLOTS` in `.sandcastle/agent-workflows/agent-slot/slots.ts`. The step runs `agent-slot/wait.ts` in every agent job: `agent-review`, `agent-implement`, `agent-rebase` (only when its agent resolves), `agent-explore` and `agent-implement-spec` (decompose and build).
- **A slot is taken** by a job still in progress whose "Wait for an agent slot" step succeeded. It is counted per job, not per run, because one `agent-rebase` run holds a job per pull request. The slot is held until the job ends, so the steps after the agent count too.
- **The runs that wait go in the order they started waiting**: a job starts when the slots taken, plus the jobs that started waiting before it, are fewer than the cap. Ties go to the lower job id, so every waiting job works out the same order.
- **A job takes a slot only once GitHub lists it as waiting, and only after two checks in a row find one free**, 15 seconds apart. GitHub's answer lags behind the runners; a job that does not see itself yet, or that saw a free slot once, checks again before it starts.
- **It counts with the `GITHUB_TOKEN`**, given `actions: read`, not with `FACTORY_PAT`: the step runs code from the checkout, which on a pull request is code an agent wrote. It reads the in-progress runs of the `agent-*` workflows, then the jobs of each. The Actions API lists no jobs across runs, so that is one call per run, and the `GITHUB_TOKEN` has 1,000 calls an hour for the whole repository: the first job in line checks every minute, the one behind it every two, and so on.
- **The wait gives up after 180 minutes**, with an error that says no agent slot came free; the job's failure path then marks it blocked as for any other failure. Each agent job's timeout is its old one plus those 180 minutes.

## Considered options

- **One `concurrency:` group for every agent run.** Rejected: GitHub keeps at most one pending run per group, and a newer one cancels it, so the third label of a burst silently cancels the second.
- **Let the `agent:queued` label carry the wait**, with a scheduled workflow starting the queued runs. It needs one more workflow and a schedule, and a run would start up to a cron tick late; the step keeps the wait inside the run the label started.
- **Count with `FACTORY_PAT`.** Its rate limit is higher, but no step that runs code an agent wrote may hold it.
