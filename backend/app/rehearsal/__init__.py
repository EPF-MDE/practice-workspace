"""The Rehearsal's pages: one long page per Competency, its locked answers, its
questions.

The page API sends the Student's Group's content with every answer block
replaced by a locked marker, until that Student's own answer to the step is
stored: the answer never leaves the server before (#460, user story 19).
A step that waits for an earlier step's answer (`after=`) sends only its
shared Markdown and a waiting marker until that answer is stored, and refuses
an answer before then (#460, user story 26).
A drawing step works the same way: its Reference Drawing and check points
are released once the Student's drawing is stored, and come back in the
response to that send.
Every write checks the cut-off dates first, and the Store is written only on a
send: drafts stay in the browser.
"""

# Importing the files of routes adds them to `router`, in this order.
from ._internal import answers, closing, evidence_panel  # noqa: F401
from ._internal.router import router

__all__ = ["router"]
