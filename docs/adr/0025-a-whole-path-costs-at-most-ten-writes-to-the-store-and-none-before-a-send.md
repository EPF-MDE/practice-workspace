# A whole Path costs at most ten writes to the Store, and none before a Send

Every write to the GitHub Store is a content-generating request, which GitHub's secondary rate limit counts, and a Course's Students all write to one repository. **So a Student's whole Path through one Competency makes at most ten writes to the Store, and none before a Send: signing in writes only the first time, when the GitHub Store opens the Student's issue, once per Course; and the closing step is one Send (ADR-0014) that carries the Evidence Plan's confirmation, its example for the Eval, the Evidence panel snapshot and any Evidence Project declaration.**

- **The budget counts** every Step with fields answered (the Transfer included), the redraw sent (not the optional one: two files and a comment), two questions, the Self-assessment with the missed check points the browser kept, then the closing step's one Send. Drafting the Evidence Plan while the Student rates each point writes nothing.
- **The closing step reads nothing again.** The Evidence panel it stores is the one the Student was shown, from the stored Repository reading, not a fresh read of their Evidence Project.
- **A declaration sent after the closing step is its own Send.**
- **Tests guard the budget on both Stores**, the in-memory one and the GitHub one through `FakeGitHub` (ADR-0024): `test_a_full_competency_path_makes_at_most_10_writes_and_none_before_a_send` in `backend/tests/test_store_api.py`, and the closing-step tests in `backend/tests/test_evidence_project.py`.
