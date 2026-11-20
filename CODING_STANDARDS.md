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

## A Deep Module: a small interface, a lot behind it

Each subpackage of `app` is a Deep Module. Its `__init__.py` is its
interface: the names listed in its `__all__` are everything a caller needs to
read. A public submodule, one without a leading `_`, adds to that interface,
so keep them few. Everything else lives under `_internal/`, where the module's
files import each other freely. `npm run check` refuses any import past the
interface, a star re-export and a cycle between modules. It cannot tell
whether the module is deep. These are findings:

- a name in the interface that only one caller needs, or that shows how the
  module works rather than what it does;
- a public function that only passes its arguments on to `_internal/`, where a
  re-export would do;
- two modules a caller must always use together to do one thing.
