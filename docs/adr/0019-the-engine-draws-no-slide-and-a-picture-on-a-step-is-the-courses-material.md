# The Engine draws no slide, and a picture on a Step is the Course's material

Supersedes [ADR-0010](./0010-the-opening-screen-redraws-the-software-factory-slide-never-shows-it.md).

The opening screen drew one Course's slide, a redraw of a third-party talk's slide annotated with that Course's Competencies, in the front end's own code. The Engine is public and knows no Course ([ADR-0001](./0001-one-public-engine-and-one-instance-per-course.md)), so no Course's picture belongs in it, and a second Course could neither drop that slide nor show its own. **So the Engine draws no slide: a picture is a Course's material, a plain Markdown image in a Step, `![what it shows](images/<file>)`, its path relative to the Course folder, and the Engine serves it from that Course folder's `images/` folder only. A picture the Course does not own is a credited redraw, never the original: the Course redraws it, credits it beside the image with a link to its source, and never puts the original in its Course folder.**

- **Only the images the served material shows are served.** Loading reads the PNG, JPEG, GIF, WebP and SVG files under `images/` once, keeps those an intro or a Step shows once the Instructor Material is left out, and `/api/course/images/<file>` answers a name from that list and nothing else, to a signed-in Student. An image only the Instructor Material shows, or that nothing shows, is never sent. No path, with `..`, absolute or naming another file of the Course folder, reaches the disk.
- **A missing image is a content problem.** `verify`, and the start it shares its loading with, refuse an image the content names and `images/` does not hold, and an image outside `images/`, naming the file and the Step.
- **The rights constraint moves with the picture.** It was the Engine's, for one slide; it is now each Course's, for every picture its Course folder carries. The Engine's own Demo course carries only pictures it drew.
- **An SVG is served as an image, not a page.** It is sent with a Content Security Policy that sandboxes it and runs no script, should a Student open it on its own.

## Considered options

- **Keep a slide component in the front end, configured by the Course folder.** Rejected: a component per kind of picture, and still one Course's idea of the opening screen in the Engine.
- **Serve the whole Course folder statically.** Rejected: it would serve the settings and the Instructor Material that loading strips from the content.
