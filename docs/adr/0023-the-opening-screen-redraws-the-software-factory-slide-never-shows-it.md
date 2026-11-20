# The opening screen redraws the Software Factory slide, never shows it

The Engine's opening screen shows "A Software Factory Circa 2022", annotated with the Competencies. The original is the final slide of a third-party talk, which the Engine has no right to republish. **So `SoftwareFactory` in `frontend/src/components/SoftwareFactory.tsx` redraws it as SVG, never shows the original, and credits it below the drawing with a link to the talk (`Credit`).**

- The annotations, the Competency regions and their notes, are the Engine's, not the talk's.
