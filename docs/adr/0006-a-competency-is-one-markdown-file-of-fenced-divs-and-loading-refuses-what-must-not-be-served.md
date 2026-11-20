# A Competency is one Markdown file of fenced divs, and loading refuses what must not be served

The Instructor writes and reviews a Course's material like any other document, and the Engine must never send a Student a Locked answer, Instructor Material or a figure the Instructor has not validated yet by mistake. **So each Competency is one Markdown file in the Course folder, with front matter and pandoc-style fenced divs, read once at start; loading refuses at start any file that could serve what it must not; and the back end renders the Markdown to HTML with raw HTML disabled, which the front end sets as it is.** [`demo-course/`](../../demo-course/) shows the format, and loading's error names what it refuses.

- **The two halves of rendering go together.** Turning raw HTML on in the back end's renderer would make the front end's `dangerouslySetInnerHTML` an injection point.
