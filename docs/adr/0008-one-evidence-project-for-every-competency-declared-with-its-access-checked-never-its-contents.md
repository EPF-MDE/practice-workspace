# One Evidence Project for every Competency, declared with its access checked, never its contents

A Student may put their evidence in another repository than the one the Roster names, until the Reading Day. As they declare it, they need to know whether the Reading Day will be able to read it. Reading its contents at that point would read a repository the Student has not yet agreed to show, and GitLab gives the Practice workspace no way to check. **So a Student declares one Evidence Project for every Competency, and a declaration checks access only, never contents: a GitHub repository is readable when it is public or when the Student Connector (ADR-0003) is installed on it, and a GitLab project gets no check, only the instruction to give the Instructor Reporter access. Each Evidence panel checks that access again on every reading**, since the Student Connector may have been installed since.

- **The access check never requests `/contents`.** It asks GitHub whether the App is installed on the repository, then whether the repository is public.
- **An access it could not check reads as not readable yet**, never as readable.

## Amended: what is read when a Student declares nothing

This decision first assumed that the Roster names a repository for every Student. A Course without such repositories cannot name one, so **the Course folder's settings say what is read when a Student declares no Evidence Project, in `read_when_none_declared`**:

- **`roster`**: the repository the Roster names for them, as above. The Roster must name one on every row, and a declaration of that same repository reads as no change.
- **`nothing`**: there is none. The Roster names no Evidence Project, and a Student's Evidence Project is only the one they declare. Until they do, nothing is read: their Evidence panel asks them to declare it, and the Reading Day's batch lists them as not declared. Withdrawing a declaration takes them back to nothing.
