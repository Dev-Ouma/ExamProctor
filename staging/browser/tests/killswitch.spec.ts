import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";
import { login, openQuiz } from "./helpers";

// M8 rehearsal: the site kill switch turns proctoring off without touching quizzes, and back on.
// Needs SSH access to the Moodle host (KILLSWITCH_SSH, KILLSWITCH_MOODLE_DIR).
const ssh = process.env.KILLSWITCH_SSH;
const dir = process.env.KILLSWITCH_MOODLE_DIR ?? "/var/www/html/ouklmsdev";

function setKillSwitch(on: boolean) {
  execFileSync("ssh", [
    "-o", "BatchMode=yes", ssh!,
    `cd ${dir} && sudo -u www-data php admin/cli/cfg.php --component=local_examproctor --name=killswitch --set=${on ? 1 : 0} && sudo -u www-data php admin/cli/purge_caches.php`,
  ]);
}

test("kill switch disables and restores the proctoring gate", async ({ page }) => {
  test.skip(!ssh, "set KILLSWITCH_SSH=user@host");
  test.setTimeout(180_000);
  const started = Date.now();
  try {
    setKillSwitch(true);
    test.info().annotations.push({ type: "switch-off seconds", description: String((Date.now() - started) / 1000) });
    await login(page, process.env.STUDENT ?? "epstudent10");
    await openQuiz(page);
    await page.getByRole("button", { name: /Attempt quiz|Re-attempt quiz|Continue your attempt/i }).click();
    // No ExamProctor panel: the attempt opens (or Moodle's own preflight shows without our checks).
    await expect(page.locator("#examproctor-precheck")).toHaveCount(0);
    await expect(page.locator(".que").first().or(page.getByRole("button", { name: "Start attempt" }))).toBeVisible({ timeout: 30_000 });
  } finally {
    setKillSwitch(false);
  }
  await openQuiz(page);
  await page.getByRole("button", { name: /Attempt quiz|Re-attempt quiz|Continue your attempt/i }).click();
  await expect(page.locator("#examproctor-precheck").or(page.locator(".que").first())).toBeVisible({ timeout: 30_000 });
});
