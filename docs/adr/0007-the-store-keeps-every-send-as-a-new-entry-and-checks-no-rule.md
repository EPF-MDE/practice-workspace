# The Store keeps every Send as a new entry, and checks no rule

The Store holds what every Student sends. Callers need a Student's current state, and the Instructor needs to see how it got there. The rules on what may be sent and when (the Close, the Reading Day, what a Step accepts) change with the Course and the Practice, not with how the Store keeps things. **So each `save_*` of the Store is one Send: it appends one new dated entry and never rewrites an earlier one, a Student's current state is the latest entry of each kind, and the Store checks no date and no content: its callers decide what may be sent, and when.**

- **The Store speaks the domain.** Its interface, `app.store.Store`, reads a Student's record and saves an answer, a drawing, a Self-assessment, an Evidence Plan, a declaration, a question or an Evidence panel snapshot; it never names its backend.
- **Two implementations, one contract.** `InMemoryStore` serves the tests and local runs, and is lost when the process stops; `GitHubStore` serves deployed Instances (ADR-0008). The Store's contract suite, `backend/tests/store_contract/`, runs the same scenarios on both.
- **Versions are counted per thing.** A version is counted per kind, Competency and key (`Entry.version`), and a record lists its entries oldest first (`Record`); `Record.latest` is the current state of one thing, `Record.history` every version of it.
- **Rules live with the request.** A rule such as "after the Close a level only moves up" lives in the Deep Module that answers the request, never in the Store.
