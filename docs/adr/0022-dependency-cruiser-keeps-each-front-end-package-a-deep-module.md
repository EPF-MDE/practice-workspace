# dependency-cruiser keeps each front-end package a Deep Module

The back end's subpackages are Deep Modules, reached only through their public names, and `tach` enforces it. **So each folder under `frontend/src/packages` is a Deep Module too: its root files are its entry points, the only way in, and everything in its subfolders (by convention `lib/` and `tests/`) is private. `frontend/.dependency-cruiser.cjs` enforces it, with the boundary rules of [Matt Pocock's setup-ts-deep-modules skill](https://github.com/mattpocock/skills/tree/main/skills/in-progress/setup-ts-deep-modules).**

- A package is one immediate child folder of `src/packages`, with no nesting; adding a package, or a folder inside one, needs no edit to the config.
- Code outside every package reaches a package only through its entry points. A package's own files import each other freely, and reach other packages only through their entry points.
- A package's tests reach other packages, and their own, only through entry points, plus their own `tests/` folder; a `tests/` folder is reachable only from tests.
- The same config also forbids cycles, imports of what is not there, and development dependencies in shipped code.
- No layering rule is set: any package may depend on any other through its entry points, as long as there is no cycle.
- The front end's `lint:boundaries` script runs it, and `npm run check` runs that.
