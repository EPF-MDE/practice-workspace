# The server withholds each Locked answer until the Student's own answer is stored

A Student should give their own answer to a Step before they see the Instructor's. Hiding the answer in the browser would still send it. **So the page API in `app.practice` (`competency_page`) sends the Student's Group's content with every answer block replaced by a locked marker until that Student's own answer to the Step is stored: a Locked answer never leaves the server before.**

- `_unlocked` in `backend/app/practice/_internal/steps.py` decides it. An answer block is released once the Student's answer to its Step is stored. In a drawing Step, the Reference Drawing, with its check points, and any answer block are released once the Student's drawing is stored (ADR-0012).
- So a drawing Step may hold an answer block without any field: `_check` in `backend/app/content/_internal/check.py` refuses an answer block without a field only in an answer Step.
- The Send that releases them returns them: `send_answer` and `send_drawing` answer with the released blocks, so the page needs no second request.
- A Step that waits for an earlier Step's answer (`after=`, ADR-0010) sends only its shared Markdown and a waiting marker until that answer is stored, withholding its Group blocks and fields (`_waits_for`), and `send_answer` refuses an answer to it before then with 409.
- Every write checks its date before it writes: an answer, a question or a drawing is refused after the Close, and the closing step's Sends after the Reading Day (ADR-0013). The Store is written only on a Send: drafts stay in the browser (ADR-0015).
