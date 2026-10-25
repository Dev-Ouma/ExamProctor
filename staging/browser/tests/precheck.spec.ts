import { expect, test } from "@playwright/test";

const PASSWORD = process.env.SEED_USER_PASSWORD ?? "Staging#2026";

async function login(page, username: string) {
  await page.goto("/login/index.php");
  await page.fill("#username", username);
  await page.fill("#password", PASSWORD);
  await page.click("#loginbtn");
  await expect(page).not.toHaveURL(/login\/index\.php/);
}

async function openQuiz(page) {
  await page.goto("/course/search.php?search=EP-STAGING-101");
  await page.click("text=ExamProctor Staging 101");
  const quiz = page.locator('a[href*="/mod/quiz/view.php"]', { hasText: "Proctored practice quiz" }).first();
  await page.goto((await quiz.getAttribute("href"))!);
}

test("student passes the ExamProctor checks and the attempt starts", async ({ page }) => {
  await login(page, process.env.STUDENT ?? "epstudent02");
  await openQuiz(page);
  await page.getByRole("button", { name: /Attempt quiz/i }).click();

  const panel = page.locator("#examproctor-precheck");
  await expect(panel.getByRole("button", { name: "I agree" })).toBeVisible();
  const start = page.locator("form#mod_quiz_preflight_form [name=submitbutton]");
  await expect(start).toBeDisabled();

  await panel.getByRole("button", { name: "I agree" }).click();
  await panel.getByRole("button", { name: "Allow camera" }).click();
  await expect(panel.getByText("Done").first()).toBeVisible();
  await panel.getByRole("button", { name: "Share your whole screen" }).click();
  await panel.getByRole("button", { name: /Run the checks|Try again/ }).click();

  await expect(panel.getByRole("status")).toContainText(/All checks passed|You cannot start yet/, { timeout: 30_000 });
  const outcome = await panel.getByRole("status").innerText();
  test.info().annotations.push({ type: "outcome", description: outcome });
  if (outcome.includes("cannot start")) {
    throw new Error(`Pre-check blocked in this browser: ${outcome}`);
  }
  await expect(start).toBeEnabled();
  await start.click();
  await expect(page).toHaveURL(/\/mod\/quiz\/attempt\.php/);
});

test("forging the Start click without checks is refused by Moodle", async ({ page }) => {
  await login(page, "epstudent03");
  await openQuiz(page);
  await page.getByRole("button", { name: /Attempt quiz/i }).click();
  const start = page.locator("form#mod_quiz_preflight_form [name=submitbutton]");
  await start.evaluate((el: HTMLInputElement) => (el.disabled = false));
  await start.click();

  await expect(page.getByText("Finish the ExamProctor checks above")).toBeVisible();
  await expect(page).not.toHaveURL(/\/mod\/quiz\/attempt\.php/);
});
