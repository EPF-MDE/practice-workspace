import { expect, test } from "@playwright/test";
import { openCompetency, path, signIn } from "./helpers/path";

const MINUTES: Record<string, number> = { C1: 30, C2: 50, C3: 20 };

test("the Path's times come from the minutes the Course gives each Competency", async ({
  page,
}) => {
  await page.route("**/api/course", async (route) => {
    const response = await route.fetch();
    const course = await response.json();
    for (const competency of course.competencies)
      competency.minutes = MINUTES[competency.id];
    await route.fulfill({ response, json: course });
  });
  await signIn(page, 1001);

  await openCompetency(page, "C2");

  await expect(page.getByTestId("time-spent")).toContainText("out of 50");
  await expect(page.getByTestId("time-session")).toContainText(
    "C1 0:00–0:30, C2 0:30–1:20, C3 1:20–1:40, 1:40"
  );
  await expect(path(page).getByTestId("path-read-the-pipeline")).toContainText(
    "0:30–0:35"
  );
});
