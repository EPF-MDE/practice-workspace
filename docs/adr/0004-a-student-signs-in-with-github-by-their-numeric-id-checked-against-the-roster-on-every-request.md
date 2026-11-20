# A Student signs in with GitHub by their numeric id, checked against the Roster on every request

A GitHub login can be renamed, and once freed it can be taken by someone else. The Practice workspace must hold no more of a Student's GitHub access than it needs, and the Instructor must be able to add or shut out a Student during a Course without touching the running Instance. **So a Student is matched on their numeric GitHub id, never on their login; the session cookie holds that id alone; no Student's token is kept once sign-in has read who they are; and every request finds the Student on the current Roster again.**

- **The Roster is `roster.csv` on the Instance's data branch**, re-read at most every five minutes, so the Instructor adds a Student by pushing to it, and removing a row signs that Student out at their next request.
- **A renamed account still gets in**; someone who took over a login on the Roster does not. `backend/tests/test_sign_in.py` guards it.
