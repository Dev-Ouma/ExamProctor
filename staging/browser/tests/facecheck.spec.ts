import { expect, test } from "@playwright/test";
import { login, openQuiz } from "./helpers";

// The pre-check runs a live face check after the camera is allowed. Chrome's fake camera shows a
// test pattern, so the expected answer here is "No face found" with a way to try again.
test("pre-check shows the live face check result", async ({ browser }) => {
  const context = await browser.newContext({ permissions: ["camera"] });
  const page = await context.newPage();
  await login(page, process.env.STUDENT ?? "epstudent16");
  await openQuiz(page);
  await page.getByRole("button", { name: /Attempt quiz|Re-attempt quiz/i }).click();
  const panel = page.locator("#examproctor-precheck");
  await panel.getByRole("button", { name: "I agree" }).click();
  await panel.getByRole("button", { name: "Allow camera" }).click();
  await expect(panel.getByText(/No face found|Face detected|too dark/)).toBeVisible({ timeout: 20_000 });
  await expect(panel.getByRole("button", { name: "Check again" })).toBeEnabled();
  if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/11-facecheck.png` });
  await context.close();
});
