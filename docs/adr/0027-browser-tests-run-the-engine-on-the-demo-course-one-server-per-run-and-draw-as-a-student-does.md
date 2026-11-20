# Browser tests run the Engine on the Demo course, one server per run, and draw as a Student does

The browser tests under `frontend/tests/` check what a Student sees on a Path, end to end. They need a back end that behaves as an Instance does, without GitHub, without PostHog and without a shared Store, and they run in parallel, on the Instructor's machine beside other runs and in CI. **So each Playwright run starts its own back end, serving the React build, on the Demo course with fake sign-in, the in-memory Store and the fake Repository reading, on a free port; each spec file signs in only Students of the Demo course's Roster that no other file signs in; and a test draws on tldraw with the mouse and the keyboard, as a Student does.**

- **`frontend/playwright.config.ts` serves the build**: run `npm run build` before the tests, as `npm run check` does. The `webServer` env sets fake sign-in, the Demo course's Roster, `WORKSPACE_STORE: "memory"`, `WORKSPACE_REPOSITORY_READING: "fake"`, and empty PostHog settings.
- **A run never reuses a server it did not start** (`reuseExistingServer: false`), so two runs side by side never meet.
- **The main process picks the port, and the workers inherit it.** Playwright reads `frontend/playwright.config.ts` in its main process and again in each worker. The main process picks a free port and leaves it in `PRACTICE_WORKSPACE_TEST_PORT`; a worker never picks its own, or it would talk to a port no server listens on.
- **Each spec file owns its Students.** The in-memory Store keeps every Send for as long as the server runs, and the files run in parallel, so a Student signed in by two files would see the other file's Sends. `sign-in.spec.ts` signs in 1001 and 1002, `path-c1.spec.ts` 1011 and 1012, `c1-redraw.spec.ts` 1021 and 1022, `path-c2.spec.ts` 1031 and 1032, `evidence-panel.spec.ts` 1041 and 1042, `path-c3.spec.ts` 1051 and 1052. A new file adds its own Students to `demo-course/roster.csv`.

## Drawing as a Student does

A redraw test must show that what a Student draws is kept, sent and compared with the Reference Drawing. `drawChain` in `frontend/tests/helpers/draw.ts` draws one labelled box per label, in rows of three, and an arrow from each box to the next, with the mouse and tldraw's keyboard shortcuts, not through tldraw's editor API.

- **Positions are in the canvas's own coordinates**, turned into the browser window's by `onPage` before each gesture, because the window may scroll while a label is edited.
- **Before each box, `drawBox` clicks an empty spot below the drawing**, clear of tldraw's panels, to give the canvas focus with nothing selected.
- **A label is typed with `page.keyboard.insertText`**, which sends no key events: typing it key by key would fire tldraw's shortcuts (`r`, `a`, and so on) on its letters.
