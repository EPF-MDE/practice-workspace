# A renamed stored field is still read under its former name

The Store never rewrites an entry: a Send stays as it was written, on GitHub, for good. In November 2026 the declaration's `note` became `what_to_read`, and its `access` became `access_when_declared` and its `repository` became `repository_path`, so that each field has one name in the API, in the code and in the Store (#49, #58). Declarations already stored, alone or inside an Evidence Plan, hold `note`, `access` and `repository`, and drafts already kept in a Student's browser hold `note`.

**So a renamed stored field is written under its new name and read under either.** `DeclarationPayload` reads `what_to_read` or `note`, `access_when_declared` or `access`, and `repository_path` or `repository`, each through a validation alias beside the field; the Store's contract suite holds both. The front end's `evidenceDrafts` does the same for a draft kept as `{url, note}`. A Repository reading kept on the data branch does the same: its Student's Group, stored as `project` until #25, is written as `group` and read under either. The former name lives in one place on each side, beside the new one.

The Evidence panel snapshot kept with an Evidence Plan is the exception: the Engine never reads it back, so it takes the new names (`what_to_read`, `declares_roster_evidence_project`, `how_to_make_readable`, and `unavailable` without `available`) and older snapshots keep the former ones. The Instructor reading snapshots across a Course reads both shapes.

## Considered options

- **Rename only the Evidence panel's response, and keep `note` in the request and the Store.** Rejected: the same idea would have two names, which CODING_STANDARDS.md's "One name per idea" refuses.
- **Rewrite the stored entries.** Rejected: the Store never rewrites a Send, and a person may point at the comment that holds it.
- **Drop drafts kept as `{url, note}`.** Rejected: a Student would lose a draft they typed and did not send, for a rename they cannot see.
