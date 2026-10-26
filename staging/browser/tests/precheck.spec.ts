import { expect, test } from "@playwright/test";
import { admitAtFaceGate, login, openQuiz } from "./helpers";

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

  // The face check has its own status line; the pre-check outcome is the last one.
  const status = panel.getByRole("status").last();
  await expect(status).toContainText(/All checks passed|You cannot start yet/, { timeout: 30_000 });
  const outcome = await status.innerText();
  test.info().annotations.push({ type: "outcome", description: outcome });
  if (outcome.includes("Finish the face check first")) {
    // Identity quiz: the fake camera shows no face, so the invigilator lets the student in.
    await admitAtFaceGate(page, process.env.STUDENT ?? "epstudent02");
    await panel.getByRole("button", { name: "Try again" }).click();
    await expect(status).toContainText("All checks passed", { timeout: 30_000 });
  } else if (outcome.includes("cannot start")) {
    throw new Error(`Pre-check blocked in this browser: ${outcome}`);
  }
  await expect(start).toBeEnabled();
  await start.click();
  // The attempt runs inside the exam shell frame.
  await expect(page.frameLocator("#examproctor-shell iframe").locator(".que").first()).toBeVisible({ timeout: 30_000 });
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
