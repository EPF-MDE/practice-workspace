// The front end's boundaries. No cycle; no import of what is not there; no
// development dependency in shipped code.
module.exports = {
  forbidden: [
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
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    tsConfig: { fileName: "tsconfig.json" },
    tsPreCompilationDeps: true,
  },
};
