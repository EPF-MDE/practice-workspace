export const SITUATIONS = {
  conflicts:
    "The rebase stopped on conflicts. `git status` shows the commit it stopped at and the conflicted files.",
  "check-fails":
    "The rebase went through, but `npm run check` fails on the result: the base changed something the pull request relies on. /tmp/check.log holds the output.",
} as const;

export type Situation = keyof typeof SITUATIONS;

export const isSituation = (value: string): value is Situation =>
  Object.hasOwn(SITUATIONS, value);
