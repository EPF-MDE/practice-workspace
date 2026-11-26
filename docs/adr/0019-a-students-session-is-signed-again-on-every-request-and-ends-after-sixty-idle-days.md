# A Student's session is signed again on every request, and ends after sixty idle days

The session cookie had a fixed lifetime of 60 days, counted from sign-in and never renewed, since Starlette signs the cookie again only when the session changes, and it changed only at sign-in. It was set to outlast one Course's Reading Day, and nothing tied it to the Course folder: on an Instance whose Reading Day falls more than 60 days after a Student signs in, the Student is signed out in the middle of the Course. **So the session is rolling: each request that finds the Student on the Roster signs the cookie again, and a session ends only after `SESSION_IDLE_LIMIT`, sixty days without a single such request.**

- **The rule lives in `app.auth`**, beside `current_student`, which signs the session again; `add_session` sets the cookie up with the limit, and `app.main` only calls it.
- **A Student who keeps coming back stays signed in for as long as the Instance runs**, past the Reading Day too, to read their own work. The Roster check of ADR-0004 still signs out a Student removed from it at their next request.
- **No restart, deploy, or change to the Course folder shortens a session**: the limit depends on nothing the Instance reads, and the cookie is signed with `WORKSPACE_SESSION_SECRET`, which an Instance on Azure must set. Only an Instance without it, run locally, signs with a new secret at each start, and so signs everyone out.
- **The session's age is read from the injected clock**, like the Close and the Reading Day, so a test moves time instead of waiting for it.
- **Sixty days idle** is longer than any break inside a Course; a Student back after one signs in again with GitHub, and loses nothing, since their work is in the Store.

## Considered options

- **Work the lifetime out from the Reading Day and the instant the app starts.** Rejected: every restart shortens the sessions already signed in, and the cookie's lifetime would depend on the Course folder's calendar.
- **Store an expiry instant in the session at sign-in, from the Reading Day.** Rejected: the cookie still needs a lifetime at least as long, the expiry must be checked on every request against the injected clock, and a Reading Day moved after sign-in leaves sessions holding the old one.
- **An explicit Instance setting for the lifetime.** Rejected: one more value an Instructor must set right for each Course, and get wrong the same way the constant did.
