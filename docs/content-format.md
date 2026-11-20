# The content format

How a Course folder writes one Competency, and what loading refuses at start. Why it is Markdown, and why loading refuses, is [ADR-0006](./adr/0006-a-competency-is-one-markdown-file-of-fenced-divs-and-loading-refuses-what-must-not-be-served.md).

## The file

- Front matter gives `competency: C<n>` and `title:`. The Markdown above the first Step is the intro, and holds no block.
- A Step is a level-2 heading with attributes: `{#id minutes=n [kind=k] [fills=point] [after=step] [optional=yes]}`.
- Directives nest: one block per Group, its directive named in the Group's settings; `field {#id kind=line|text}`, or `kind=choice options="a|b|c"` for one option to pick; `answer`; `point {#C<n>.<letter> band=...}`, its Band one of `BANDS`, with at most one `proof` and one `to-get-there {level=not-yet|understand|redo}` per level inside; and `instructor`, authoring notes stripped like HTML comments.
- A Step's kind is one of `STEP_KINDS` in `backend/app/content/_internal/model.py`: `read` or `answer` by default.
- `drawing` is a redraw (ADR-0007). It holds an `example-drawing {src=...}`, a drawing of a simpler system shown read-only at once, its body the caption; one `canvas` per Group, its body the prompt, which gives only the drawing's start and end points; and a `reference-drawing {src=...}` holding 3 to 5 (`CHECK_POINTS`) `check-point {#id point=C<n>.<letter>}`. `src` is a tldraw snapshot (JSON) inside the Course folder: `load_content` refuses one outside it. One drawing Step per Competency may be `optional=yes`, and nothing depends on it.
- `transfer`, with `fills=<point>`, has a field `#project`, empty for the Evidence Project; its answer fills that point's "To get there" in the Evidence Plan's draft.
- `closing` holds the points the Self-assessment rates, each `proof` completing "At the Eval, I will show ...".
- A Step may wait for an earlier Step that takes an answer (`after=<step>`). Until that answer is stored, the Student receives only the Step's shared Markdown and a waiting marker, never its Group blocks or fields (see Locked answer in the glossary). The marker is the Step's one `::: waiting` block, outside the Group blocks, or else a sentence naming the earlier Step. Its fields and answers sit inside the Group blocks.

## What loading refuses

An unknown directive, an unclosed block, an answer block in an answer Step without fields, a Step with one Group's block but not the other's, a wait on a Step that takes no answer, a word only Instructor Material uses (`INSTRUCTOR_MARKERS`), and `UNVALIDATED_MARKER` (`TO VALIDATE`), the marker of a figure the Instructor has not validated yet, anywhere it would be served, even in an answer: it belongs in an HTML comment. `_check` looks for both markers in what `Competency.for_group` returns for each Group.

`Competency.for_group` returns what one Group's Students may be sent, answer blocks included. Withholding them is the caller's job, through the `Answer` and `ReferenceDrawing` blocks it recognises (see Locked answer in the glossary).
