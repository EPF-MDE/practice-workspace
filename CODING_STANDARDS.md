# Coding standards

Judgement rules only: the reviewer checks these by reading. A rule a machine can check is a check in `npm run check`, not a line here.

## Tests go through the HTTP API

A test starts the app on a Course folder and asks it what a Student or the Instructor would ask: an HTTP request, and the answer it gets. It does not call a module's internals, and it does not read what the Store wrote. A test that reaches past the API breaks on every refactor and still passes when the API answers wrongly.

## A stored format is tested once, in the Store's contract suite

How an entry is written, and read back, is the Store's business. The Store's contract suite runs the same tests on every implementation of the Store, and it is the only place a stored format is asserted. Every other test reads a Student's record back through the API.

## A test checks behaviour, not wording

A test is there to fail when something stops working. A prompt, a doc, an ADR or a comment has no behaviour: a test that reads one and asserts its words fails on every rewording, and still passes when the text says something wrong. Such a test is a finding, even when a ticket changed that text. A change that is only text ships with no test; its reader is its review.

## One name per idea, the glossary's

An idea has one name, the one in [GLOSSARY.md](./GLOSSARY.md), on the screen, in the API, in the Store's entry kinds, in the code and in the tests. A word on the glossary's _Avoid_ list is a finding. A new idea gets its glossary entry in the same change that names it.

## Markdown is not hard-wrapped

A paragraph or a list item is one line, as a person types it in an editor that soft-wraps. A line break inside a paragraph is a finding: it makes every edit reflow the lines after it, and the diff shows lines that did not change. Biome formats Markdown but leaves line breaks where they are, so nothing else catches them.

## A Deep Module: a small interface, a lot behind it

Each subpackage of the back end's `app`, and each folder under the front end's `src/packages`, is a Deep Module. Its interface is everything a caller needs to read:

- In the back end, the names in `__init__.py`'s `__all__`, plus any submodule without a leading `_`. Everything else lives under `_internal/`.
- In the front end, the files at the package's root: several small entry points rather than one `index.ts` re-exporting everything. Everything else lives in subfolders: `lib/` for the implementation, `tests/` for its tests, which go through the entry points too.

Behind the interface, the module's files import each other freely. `npm run check` refuses any import past an interface, and any cycle. It cannot tell whether the module is deep. These are findings:

- a name or an entry point that only one caller needs, or that shows how the module works rather than what it does;
- a public function that only passes its arguments on to the implementation, where a re-export would do;
- two modules a caller must always use together to do one thing.

## Rules taken from Software Factories for Real Engineers

The rules below come from the coding standards of [Software Factories for Real Engineers](https://www.aihero.dev/cohorts/software-factories-for-real-engineers-xdy1m) ([its `CODING_STANDARDS.md`](https://github.com/ai-hero-dev/cohort-005-project/blob/4339a3095c5d85e4fb2b3b60ff6c1e6d18147180/CODING_STANDARDS.md)), rewritten for the Engine. These were left out:

- "Fail with a thrown response, not a return value": it is written for React Router's loaders and actions, and the Engine has neither.
- "A route does not query data a module owns": in the Engine, `npm run check` refuses any import past a Deep Module's interface, and "A Deep Module: a small interface, a lot behind it" holds what is left to judge.
- "Arrange tests through the module under test": "Tests go through the HTTP API" replaces it.
- "Client and server share one normalisation": its fix is one function both sides import, and the Engine's back end is Python while its front end is TypeScript.

### Related writes land together, or not at all

Two entries that must both land, or neither, go to the Store in one write. If the second fails once the first has landed, the Store holds a state nothing knows how to read.

### Do not read in a loop

One read of the Store, or one call to GitHub, per item is N+1 reads. Read everything the request needs at once, then work on it in memory.

### Paginate anything that can grow

A list whose length grows with the Roster, or with how long a Course has run, is read and answered in parts of a bounded size. It is fine on the Demo course and too slow on a real Course.

### Never delete what a person can point at

If a Send, an entry or anything else is referenced, or a person has a link to it, it is not deleted. A later entry in the Store says it no longer stands, and reads leave it out.

### A value the code compares against is defined once

A kind or a state the code compares against, such as a Store entry's kind, is defined once on each side, in the Deep Module that owns it: an enum in the back end, a union type in the front end. It is not a literal repeated across files, where one spelt differently never matches and nothing says so.

### Inject the clock

Whether the Close or the Reading Day has passed depends on the time. Code that reads the clock itself cannot be tested at a fixed instant: it takes the instant as an argument, and only the edge of the back end reads the clock.

### Keep secrets on the server

Anything the front end holds, the Student can read. A token or a key is read only in the back end, and never sent to the front end. The same goes for a Locked answer: the back end withholds it until the Student's own answer to that Step is stored.

### Derive, do not store

If a value can be worked out from one already held, work it out. Storing it gives two values that must agree, and one day they will not. A Student's current state is derived from the Store's latest entries; it is not a second copy kept beside them.

### Parse untrusted input with a schema, at the edge

A request's body and parameters, the Course folder and what GitHub answers go through a schema before the code uses them: zod in the front end, a validating model in the back end. Parse once, at the boundary, coercing numbers through the schema; past it the value has a type, and nothing checks it again.

### Check permission on every request that changes something

Each request that changes something checks, by itself, that the person sending it may: a Student sends only for themselves, and only the Instructor does what is the Instructor's. A check on the request that shows the screen does not protect the one that changes the Store.

### A decision lives in an ADR, not a comment

Name and extract until the code needs no comment. A decision goes in an ADR in [docs/adr/](./docs/adr/), where it can be found and superseded; a comment holding one goes stale the moment someone changes the code without reading it. When a change touches a comment that records a decision, it deletes the comment, writes the ADR if the decision still stands, and names both in the pull request. Several such comments in one area mean decisions are skipping the ADR: the pull request flags that too.

### A split the token check forced is in scope

`npm run check` and the pre-commit hook refuse any file over 5000 tokens, so a one-line fix to a large file arrives with a split. The split belongs to the change. Review it as a move: the code arrives unchanged in its new place, and the new files follow every rule here.

### Front end: no side effect in the render path

Rendering works out what to show; it does not do anything. A request, a write or a timer belongs in an effect or an event handler.

### Front end: key a controlled field by the record it edits

A field whose value lives in `useState` keeps it when the record underneath changes. Give its component a `key` of the record it edits, such as the Step its answer is for, so moving to another one starts a fresh draft instead of sending the last one's.
