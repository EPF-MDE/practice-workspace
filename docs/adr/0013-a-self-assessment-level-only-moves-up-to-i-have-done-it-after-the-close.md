# A Self-assessment level only moves up to "I have done it" after the Close

The closing step asks a Student to rate each point of a Competency. Before the Close it is a working tool. Between the Close and the Reading Day it must not be rewritten to look better than the Practice was, yet a Student who finishes the work still deserves to say so. **So `app.closing` holds these rules as pure functions, with no Store and no HTTP, and the API turns their `Refused` into its status code.**

- One level per point, on four (`LEVELS`): _Not yet_, _I understand_, _I can redo_, _I have done it_. _I have done it_ needs a link to the Student's work on GitHub or GitLab (`clean_levels`), and no other level keeps a link. The point's proof sentence says what that link points to.
- Before the Close, every level moves freely. Between the Close and the Reading Day (`check_move`), a level already given only moves up to _I have done it_, with a link, and every other level stays as it was. A point with no level yet takes its first one freely, dated like any move, and once stored it is held by the same rule. After the Reading Day nothing changes (403).
- A point's date (`since`) is the first Send of the latest unchanged run of its level and link, not the first time it ever took that level.
- The page receives `closed` and `reading_day_passed` so that it shows the same rules before a Send is refused.
