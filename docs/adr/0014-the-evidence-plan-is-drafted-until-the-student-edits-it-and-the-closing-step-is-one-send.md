# The Evidence Plan is drafted until the Student edits it, and the closing step is one Send

The closing step of a Practice Path asks for a level per point (ADR-0013), the Evidence Plan, an example for the Eval and, optionally, an Evidence Project. A Student writes an Evidence Plan more readily from a proposal than from a blank page, but the proposal must not pass for their own work, and it must follow their levels as they change. And stored as separate Sends, the plan, the Evidence panel it was written against and the declaration could land one without the next. **So `draft` in `app.closing` proposes the Evidence Plan from the levels, and the text stays a draft, redrafted from the levels, until the Student edits it; and the closing step is one Send, an `evidence-plan` entry that confirms the plan with its example and also carries the Evidence panel shown and any Evidence Project declared there.**

## The draft

- The draft has one block per point rated and not done: its id, Band, level and statement, the proof to show at the Eval, how to get there at that level, and where. A Transfer the Student sent fills its point's "To get there" (`_transfer` in `backend/app/practice/_internal/review.py`). The proof is joined to "At the Eval, I will show" with `_uncapitalised`, which lowers a first capital but leaves an acronym such as "README" as it is.
- The draft is computed, never stored. `usePlan` in `frontend/src/practice/closing/useEvidencePlan.ts` asks `PracticeService.draftEvidencePlan` for it on every change of the levels the browser holds, and `draft_evidence_plan` drafts from those levels, not yet sent, and stores nothing.
- Once the Student edits the text (`closingDrafts.setPlan`), their text wins over the draft.
- An untouched plan stays a draft even once confirmed: the browser sends it with `drafted: true`, and `_drafted` in `review.py` also marks a text `drafted` when it equals the draft from the levels stored. A stored plan marked `drafted` keeps following the levels; only an edit makes it the Student's text.

## The closing step's Send

- `close_competency` stores the Evidence Plan confirmed, one example for the Eval, the Evidence Project declared there if any, and `evidence_panel_snapshot`, the Evidence panel as shown. It refuses before the Self-assessment is stored (409), since the plan is drafted from it.
- `useSendPlan` confirms with `PracticeService.closeCompetency` while the plan is not confirmed or its example changed, and sends `PracticeService.sendEvidencePlan`, the text only, after that. `send_evidence_plan` stores a new dated version that carries the example and the confirmation over.
- An Evidence Project declared in the closing step before the plan is confirmed rides with that confirming Send (`declaration` in its body), so a first-time Student sends once; it is every Competency's Evidence Project. After the confirmation, `EvidenceProject` in `frontend/src/practice/evidence/EvidenceProject.tsx` makes a change or a withdrawal its own Send, until the Reading Day.
- `Record.declaration()` in `backend/app/store/_internal/model.py` reads the Evidence Project declared now from either a `declaration` entry or a closing step's `evidence-plan` entry, whichever is later.
- A separate `evidence-panel-snapshot` kind (`Kind.EVIDENCE_PANEL_SNAPSHOT`) remains for a panel stored on its own.
- A Step's point blocks are shown only by the closing step's Self-assessment form: `StepBlock` in `frontend/src/practice/StepBlock.tsx` renders nothing for a `point` block.
