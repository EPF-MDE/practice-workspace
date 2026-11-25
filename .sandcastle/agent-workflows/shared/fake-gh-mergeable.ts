import { writeFileSync } from "node:fs";
import { join } from "node:path";

export type Mergeable = "MERGEABLE" | "CONFLICTING" | "UNKNOWN";

export const answersMergeable = (
  dir: string,
  pr: number,
  states: Mergeable[]
): string => {
  states.forEach((state, index) => {
    writeFileSync(
      join(dir, `mergeable-${index}.json`),
      JSON.stringify({ mergeable: state })
    );
  });
  writeFileSync(join(dir, "asked"), "0");
  return `  "pr view ${pr} --json mergeable")
    asked=$(cat "${dir}/asked")
    echo $((asked + 1)) > "${dir}/asked"
    last=${states.length - 1}
    [ "$asked" -gt "$last" ] && asked=$last
    cat "${dir}/mergeable-$asked.json" ;;`;
};
