# Coding standards

Judgement rules only: the reviewer checks these by reading. A rule a machine
can check is a check in `npm run check`, not a line here.

## Tests go through the HTTP API

A test starts the app on a Course folder and asks it what a Student or the
Instructor would ask: an HTTP request, and the answer it gets. It does not
call a module's internals, and it does not read what the Store wrote. A test
that reaches past the API breaks on every refactor and still passes when the
API answers wrongly.

## A stored format is tested once, in the Store's contract suite

How an entry is written, and read back, is the Store's business. The Store's
contract suite runs the same tests on every implementation of the Store, and
it is the only place a stored format is asserted. Every other test reads a
Student's record back through the API.

## One name per idea, the glossary's

An idea has one name, the one in [GLOSSARY.md](./GLOSSARY.md), on the screen,
in the API, in the Store's entry kinds, in the code and in the tests. A word
on the glossary's _Avoid_ list is a finding. A new idea gets its glossary
entry in the same change that names it.
