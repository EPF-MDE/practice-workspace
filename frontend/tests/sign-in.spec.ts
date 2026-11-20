import { expect, type Page, test } from "@playwright/test";

const ADA = { id: 1001, name: "Ada Lovelace", project: "OcéENS" };
const GRACE = { id: 1002, name: "Grace Hopper", project: "MATHutrice" };

async function signIn(page: Page, githubId: number) {
  await page.goto("/sign-in");
  await expect(
    page.getByRole("link", { name: "Sign in with GitHub" })
  ).toBeVisible();
  await page.goto(`/auth/login?github_id=${githubId}`);
}

test("the sign-in page says what is stored, where, who reads it, and until when", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page).toHaveURL(/\/sign-in$/);
  await expect(
    page.getByText(/stored on GitHub, in the United States/)
  ).toBeVisible();
  await expect(page.getByText(/only the Instructor reads/)).toBeVisible();
  await expect(page.getByText(/deleted after the verdict/)).toBeVisible();
});

for (const student of [ADA, GRACE]) {
  test(`${student.name} lands on the annotated slide with their Group's Project`, async ({
    page,
  }) => {
    await signIn(page, student.id);

    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByTestId("project")).toHaveText(student.project);
    const slide = page.getByRole("img", {
      name: "A Software Factory Circa 2022, annotated with C1, C2 and C3",
    });
    await expect(slide).toBeVisible();
    for (const id of ["C1", "C2", "C3"]) {
      await expect(slide.locator(`[data-competency="${id}"]`)).toBeVisible();
    }
    const citation = page.getByRole("link", {
      name: "Why Software Factories Fail",
    });
    await expect(citation).toHaveAttribute("href", /youtube\.com.*t=220/);
    await expect(page.getByText(/Watch 3:40 to 5:45/)).toBeVisible();

    await page.reload();
    await expect(page.getByTestId("project")).toHaveText(student.project);
  });
}

test("someone not on the roster is told so, and whom to ask", async ({
  page,
}) => {
  await signIn(page, 999);

  await expect(page).toHaveURL(/\/not-on-the-list$/);
  await expect(
    page.getByRole("heading", { name: "You are not on the Course's list" })
  ).toBeVisible();
  await expect(page.getByText(/Ask the Instructor to add you/)).toBeVisible();
  await expect(page.getByText(/user-999/)).toBeVisible();
});

test("signing out returns to the sign-in page", async ({ page }) => {
  await signIn(page, ADA.id);
  await page.getByRole("button", { name: "Sign out" }).click();

  await expect(page).toHaveURL(/\/sign-in$/);
  await page.goto("/");
  await expect(page).toHaveURL(/\/sign-in$/);
});
