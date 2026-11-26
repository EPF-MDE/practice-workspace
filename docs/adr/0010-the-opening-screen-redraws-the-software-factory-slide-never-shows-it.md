# The opening screen redraws the Software Factory slide, never shows it

**Status:** superseded by [ADR-0019](./0019-the-engine-draws-no-slide-and-a-picture-on-a-step-is-the-courses-material.md). The Engine no longer draws this slide; its rights constraint now holds for every picture a Course folder carries.

The Engine's opening screen shows "A Software Factory Circa 2022", annotated with the Competencies. The original is the final slide of a third-party talk, which the Engine has no right to republish. **So `SoftwareFactory` in `frontend/src/components/SoftwareFactory.tsx` redraws it as SVG, never shows the original, and credits it below the drawing with a link to the talk.** The annotations, the Competency regions and their notes, are the Engine's, not the talk's.
