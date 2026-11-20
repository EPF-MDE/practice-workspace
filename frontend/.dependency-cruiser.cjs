// @ts-check
// The front end's boundaries. Each folder under src/packages is a Deep Module:
// its root files are its entry points, the only way in; everything in its
// subfolders (by convention lib/ and tests/) is private. Adding a package, or a
// folder inside one, needs no edit here. Then: no cycle; no import of what is
// not there; no development dependency in shipped code.
// The boundary rules are those of Matt Pocock's setup-ts-deep-modules skill:
// https://github.com/mattpocock/skills/tree/main/skills/in-progress/setup-ts-deep-modules

/** Where packages live: one immediate child folder per package, no nesting. */
const R = "src/packages";

/** Anything inside a package's subfolders; its root files are not matched. */
const PACKAGE_INTERNALS = `^${R}/[^/]+/[^/]+/`;

/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: "entrypoint-boundary-from-app",
      comment:
        "Code outside every package may import a package's entry points (its root files), never its subfolders.",
      severity: "error",
      from: { pathNot: `^${R}/` },
      to: { path: PACKAGE_INTERNALS },
    },
    {
      name: "entrypoint-boundary-across-packages",
      comment:
        "A package's own files import each other freely, and reach other packages only through their entry points.",
      severity: "error",
      from: { path: `^${R}/([^/]+)/`, pathNot: `^${R}/[^/]+/tests/` },
      to: { path: PACKAGE_INTERNALS, pathNot: `^${R}/$1/` },
    },
    {
      name: "tests-through-entrypoints",
      comment:
        "A package's tests import entry points and their own tests/ fixtures, never any package's internals, not even their own.",
      severity: "error",
      from: { path: `^${R}/([^/]+)/tests/` },
      to: { path: PACKAGE_INTERNALS, pathNot: `^${R}/$1/tests/` },
    },
    {
      name: "tests-folder-is-private",
      comment: "A package's tests/ folder is reachable only from tests.",
      severity: "error",
      from: { pathNot: `^${R}/[^/]+/tests/` },
      to: { path: `^${R}/[^/]+/tests/` },
    },
    {
      name: "no-circular",
      severity: "error",
      from: {},
      to: { circular: true },
    },
    {
      name: "not-to-unresolvable",
      severity: "error",
      from: {},
      to: { couldNotResolve: true },
    },
    {
      name: "not-to-dev-dep",
      severity: "error",
      from: { path: "^src", pathNot: "\\.(spec|test)\\.(ts|tsx)$" },
      to: { dependencyTypes: ["npm-dev"] },
    },

    // Layering, off: which packages may depend on which. For example:
    // {
    //   name: "ui-may-not-depend-on-store",
    //   severity: "error",
    //   from: { path: `^${R}/ui/` },
    //   to: { path: `^${R}/store/` },
    // },
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    tsConfig: { fileName: "tsconfig.json" },
    tsPreCompilationDeps: true,
    enhancedResolveOptions: {
      extensions: [".ts", ".tsx", ".js", ".jsx", ".json"],
    },
  },
};
