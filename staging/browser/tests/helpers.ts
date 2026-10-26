import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type Page } from "@playwright/test";

const PASSWORD = process.env.SEED_USER_PASSWORD ?? "Staging#2026";
const STAGING = resolve(fileURLToPath(new URL(".", import.meta.url)), "../..");

const loggedIn = new WeakMap<Page, string>();

export async function login(page: Page, username: string) {
  loggedIn.set(page, username);
  await page.goto("/login/index.php");
  await page.fill("#username", username);
  await page.fill("#password", PASSWORD);
  await page.click("#loginbtn");
  await expect(page).not.toHaveURL(/login\/index\.php/);
}

export async function openQuiz(page: Page) {
  // Deployed sites with many courses: go straight to the quiz.
  if (process.env.QUIZ_URL) {
    await page.goto(process.env.QUIZ_URL);
    return;
  }
  await page.goto("/course/search.php?search=EP-STAGING-101");
  await page.click("text=ExamProctor Staging 101");
  const quiz = page.locator('a[href*="/mod/quiz/view.php"]', { hasText: "Proctored practice quiz" }).first();
  await page.goto((await quiz.getAttribute("href"))!);
}

/** Pass the pre-checks; returns the Start button, now enabled. Chrome's fake camera shows no face,
 * so on an identity quiz an invigilator lets the student in from the live wall. */
export async function passPrechecks(page: Page) {
  await page.getByRole("button", { name: /Attempt quiz|Re-attempt quiz/i }).click();
  const panel = page.locator("#examproctor-precheck");
  await panel.getByRole("button", { name: "I agree" }).click();
  await panel.getByRole("button", { name: "Allow camera" }).click();
  await panel.getByRole("button", { name: "Share your whole screen" }).click();
  await panel.getByRole("button", { name: /Run the checks/ }).click();
  const passed = panel.getByText("All checks passed");
  const held = panel.getByText("Finish the face check first");
  await expect(passed.or(held)).toBeVisible({ timeout: 30_000 });
  if (await held.isVisible()) {
    await admitAtFaceGate(page, loggedIn.get(page)!);
    await panel.getByRole("button", { name: "Try again" }).click();
    await expect(passed).toBeVisible({ timeout: 30_000 });
  }
  const start = page.locator("form#mod_quiz_preflight_form [name=submitbutton]");
  await expect(start).toBeEnabled();
  return start;
}

/** An invigilator lets a student held at the face check in, with a reason. */
export async function admitAtFaceGate(studentPage: Page, student: string) {
  const context = await studentPage.context().browser()!.newContext({ viewport: { width: 1366, height: 1000 } });
  const staff = await context.newPage();
  await login(staff, process.env.INVIGILATOR ?? "epinvigilator");
  await openQuiz(staff);
  await staff.getByRole("menuitem", { name: /More/ }).click();
  await staff.getByRole("menuitem", { name: "Proctoring report" }).click();
  const liveTab = staff.getByRole("tab", { name: "Live wall" });
  if (await liveTab.isVisible().catch(() => false)) await liveTab.click();
  // Earlier runs may leave held sessions for the same student; let them all in.
  const held = staff
    .getByRole("article", { name: new RegExp(`Synthetic Student ${student.slice(-2)}`) })
    .filter({ hasText: /Held at face check/ });
  await expect(held.first()).toBeVisible({ timeout: 30_000 });
  while ((await held.count()) > 0) {
    const card = held.first();
    await card.getByRole("button", { name: "Let in without face check" }).click();
    await card.getByLabel("Let in without face check: reason").fill("End-to-end test: fake camera has no face");
    await card.getByRole("button", { name: "Send let in without face check" }).click();
    await expect(staff.getByText("Let in without face check sent.").first()).toBeVisible();
    await staff.waitForTimeout(1_000);
  }
  await context.close();
}

/** SSH target of a deployed host (REMOTE_SSH=user@host); unset for the local Docker staging. */
export const REMOTE_SSH = process.env.REMOTE_SSH;
export const REMOTE_MOODLE_DIR = process.env.REMOTE_MOODLE_DIR ?? "/var/www/html/ouklmsdev";
const REMOTE_SERVICE_DIR = process.env.REMOTE_SERVICE_DIR ?? "/opt/examproctor";

/** Run SQL against the service database: local staging, or the deployed host over SSH. */
export function serviceSql(sql: string): string {
  if (REMOTE_SSH) {
    // SQL goes through stdin, so no shell quoting on the remote side.
    return execFileSync(
      "ssh",
      ["-o", "BatchMode=yes", REMOTE_SSH,
        `cd ${REMOTE_SERVICE_DIR} && sudo docker compose exec -T service-db psql -U examproctor -tA -f -`],
      { encoding: "utf8", input: sql },
    ).trim();
  }
  return execFileSync(
    "docker",
    ["compose", "-f", `${STAGING}/compose.yml`, "--env-file", `${STAGING}/.env`, "--env-file",
      `${STAGING}/examproctor.secrets`, "exec", "-T", "service-db", "psql", "-U", "examproctor", "-tA", "-f", "-"],
    { encoding: "utf8", input: sql },
  ).trim();
}

/** Latest finished attempt on the proctored quiz, read from the deployed Moodle over SSH. */
export function latestProctoredAttempt(): string {
  const php = `define("CLI_SCRIPT", 1); require "config.php";
echo $DB->get_field_sql("SELECT MAX(a.id) FROM {quiz_attempts} a JOIN {quizaccess_examproctor} p ON p.quizid = a.quiz AND p.enabled = 1 WHERE a.state = 'finished'");`;
  return execFileSync(
    "ssh",
    ["-o", "BatchMode=yes", REMOTE_SSH!, `cd ${REMOTE_MOODLE_DIR} && sudo -u www-data php`],
    { encoding: "utf8", input: `<?php ${php}` },
  ).trim();
}
