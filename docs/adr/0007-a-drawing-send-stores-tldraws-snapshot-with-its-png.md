# A drawing Send stores tldraw's snapshot with its PNG

In a drawing Step the Student redraws a system in tldraw, then compares it with the Reference Drawing. The Instructor reads a picture, and the Student must be able to draw on from any browser. **So each drawing Send stores both the PNG tldraw exported in the browser and tldraw's own snapshot, as `getSnapshot(editor.store)` returns it, as a new version each time.**

- **The snapshot is tldraw's format.** Changing the drawing library means converting every stored snapshot, or giving up drawing on from them.
- **Both files are too large for an issue comment**, so the GitHub Store writes them to the data branch, and the drawing's comment records the commit holding both (ADR-0002, ADR-0005).
