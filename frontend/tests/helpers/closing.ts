import type { Page } from "@playwright/test";
import { step } from "./path";

export type Level =
  | "Not yet"
  | "I understand"
  | "I can redo"
  | "I have done it";

/** The closing step's controls: the Self-assessment, the Evidence Plan and the Evidence Project. */
export function closing(page: Page) {
  const section = step(page, "closing");
  const evidence = section.getByTestId("evidence-project");
  return {
    section,
    plan: section.getByRole("textbox", { name: "Your Evidence Plan" }),
    rate: (point: string, level: Level) =>
      section
        .getByTestId(`point-${point}`)
        .getByRole("radio", { name: level })
        .check(),
    level: (point: string, level: Level) =>
      section.getByTestId(`point-${point}`).getByRole("radio", { name: level }),
    link: (point: string, url: string) =>
      section.getByTestId(`point-${point}`).getByRole("textbox").fill(url),
    sendSelfAssessment: section.getByRole("button", {
      name: "Send my Self-assessment",
    }),
    example: section.getByRole("textbox", {
      name: "One example you will show at the Eval",
    }),
    confirm: section.getByRole("button", { name: "Confirm my Evidence Plan" }),
    evidence,
    /** Fills in an Evidence Project and checks its access; it rides with the confirmation. */
    declare: async (url: string, note: string) => {
      await evidence
        .getByRole("textbox", { name: /its address on GitHub/ })
        .fill(url);
      await evidence
        .getByRole("textbox", { name: /A note saying what to read/ })
        .fill(note);
      await evidence.getByRole("button", { name: "Check access" }).click();
      return evidence.getByTestId("access");
    },
  };
}
