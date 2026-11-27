import { expect, type Page, test } from "@playwright/test";

const ADA = { id: 1001, name: "Ada Lovelace", group: "OcéENS" };
const GRACE = { id: 1002, name: "Grace Hopper", group: "MATHutrice" };

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
  test(`${student.name} lands on the opening screen with their Group`, async ({
    page,
  }) => {
    await signIn(page, student.id);

    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByTestId("group")).toHaveText(student.group);

    await page.reload();
    await expect(page.getByTestId("group")).toHaveText(student.group);
  });
}

test("the opening page names the Course, as its Course folder's settings say", async ({
  page,
}) => {
  await signIn(page, ADA.id);

  await expect(
    page.getByRole("heading", { level: 1, name: "Demo course" })
  ).toBeVisible();
});

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
