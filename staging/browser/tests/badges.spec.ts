import { expect, test } from "@playwright/test";
import { latestProctoredAttempt, login, REMOTE_SSH } from "./helpers";

// Reviewers see the proctoring summary (and per-question badges) on Moodle's attempt review page.
test("attempt review page links to the proctoring report", async ({ page }) => {
  const attempt = process.env.ATTEMPT_ID ?? (REMOTE_SSH ? latestProctoredAttempt() : "");
  test.skip(!attempt, "set ATTEMPT_ID to a proctored attempt, or REMOTE_SSH to find one");
  await login(page, process.env.TEACHER ?? "epteacher");
  await page.goto(`/mod/quiz/review.php?attempt=${attempt}`);
  const summary = page.getByRole("link", { name: /Proctoring: integrity score/ });
  await expect(summary).toBeVisible();
  if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/6-review-badges.png` });
  await summary.click();
  await expect(page.getByText(/Incident report/)).toBeVisible({ timeout: 30_000 });
});
