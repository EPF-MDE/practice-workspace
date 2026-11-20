# One public engine, and one instance per course

The Practice workspace was first built inside one Course's private repository,
for that Course alone. Other courses need the same thing, and the Instructor
wants the tooling public so that it shows how they work. **So the Practice
workspace is one public Engine, this repository, and each Course runs its own
Instance of it**, with its own Course folder, apps and Store.

- **The Engine holds no Course.** It is MIT-licensed and written in English.
  It holds the Path, its Steps and Locked answers, sign-in against a Roster,
  the Store, the Self-assessment, the Evidence Plan, the Eval's ending and the
  Repository reading, plus the Demo course for its own tests. A Course's
  Groups, Competencies, levels, dates, material and drawings stay in that
  Course's private repository, read when the Instance starts.
- **A Course pins a released version.** Each tag of the Engine publishes an
  artefact. A Course deploys that version with its own Course folder to its own
  apps, with its own repository as the Store, and runs it locally on its
  Course folder to write it.
- **The Engine knows no fork.** It reads the one repository a Student declares
  as their Evidence Project. Whether that is a fork, and what is read when a
  Student declares nothing, is the Course's setting.
- **The Engine starts from a fresh history.** The repository it was first built
  in holds the Instructor's answers to each Step. Making that history public
  would show Students the answers before they give their own.
- **Its work is public, a Course's material is not.** The Engine's specs and
  tickets are generic and live here. A Course's material, and what it says of
  its Students, stays in that Course's issues, which link to the Engine's.

## Considered options

- **One hosted app serving every Course.** Rejected: it needs tenants, a shared
  Store and a production service the Instructor answers for across Courses,
  which is more than two Courses justify.
- **Keep the workspace in its first Course and copy it into the next.**
  Rejected: two copies drift, and none of it can be shown.
- **Extract it with its first repository's history, filtered.** Rejected: a
  single missed path would publish the answers.
