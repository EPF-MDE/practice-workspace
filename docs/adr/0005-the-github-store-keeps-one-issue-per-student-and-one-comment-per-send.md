# The GitHub Store keeps one issue per Student, and one comment per Send

An Instance needs its Store to outlive a restart without another service to run, and the Instructor wants to read what a Student sent where they already work. **So the GitHub Store keeps each Student's record in one issue of the Instance's repository, found again by a hidden marker holding the Student's numeric GitHub id, and each Send as one comment on it, written by the Store App (ADR-0003): a line for a person to read, then the Send as one line of JSON in a fenced block.** A drawing's files go to the data branch besides (ADR-0002).

- **Only the Store App's comments are Sends.** The Instructor may comment on an issue, and nobody can forge a Send by pasting a block.
- **A second issue drops nothing.** GitHub's label search lags seconds behind a new issue, so a restart right after a first sign-in may open a second issue for the same Student: a record is read from every issue carrying the Student's marker, merged by date.
- **An unknown kind is skipped**, so an older Engine reads a Store a newer one wrote.
- **Every Send fits one comment.** GitHub refuses a comment over 65,536 characters, and no retry fixes that. So each text a Student sends has its own limit, set so that the largest Send still fits, and the Store fails in exactly two ways, both storing nothing: unavailable (503, try again) or a Send too large (422, change it).
- **The label is a setting**, so staging's issues never mix with the Students'.
