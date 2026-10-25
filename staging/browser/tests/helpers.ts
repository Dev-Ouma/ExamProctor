import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type Page } from "@playwright/test";

const PASSWORD = process.env.SEED_USER_PASSWORD ?? "Staging#2026";
const STAGING = resolve(fileURLToPath(new URL(".", import.meta.url)), "../..");

export async function login(page: Page, username: string) {
  await page.goto("/login/index.php");
  await page.fill("#username", username);
  await page.fill("#password", PASSWORD);
  await page.click("#loginbtn");
  await expect(page).not.toHaveURL(/login\/index\.php/);
}

export async function openQuiz(page: Page) {
  await page.goto("/course/search.php?search=EP-STAGING-101");
  await page.click("text=ExamProctor Staging 101");
  const quiz = page.locator('a[href*="/mod/quiz/view.php"]', { hasText: "Proctored practice quiz" }).first();
  await page.goto((await quiz.getAttribute("href"))!);
}

/** Pass the pre-checks; returns the Start button, now enabled. */
export async function passPrechecks(page: Page) {
  await page.getByRole("button", { name: /Attempt quiz|Re-attempt quiz/i }).click();
  const panel = page.locator("#examproctor-precheck");
  await panel.getByRole("button", { name: "I agree" }).click();
  await panel.getByRole("button", { name: "Allow camera" }).click();
  await panel.getByRole("button", { name: "Share your whole screen" }).click();
  await panel.getByRole("button", { name: /Run the checks/ }).click();
  await expect(panel.getByRole("status")).toContainText("All checks passed", { timeout: 30_000 });
  const start = page.locator("form#mod_quiz_preflight_form [name=submitbutton]");
  await expect(start).toBeEnabled();
  return start;
}

/** Run SQL against the service database (staging only). */
export function serviceSql(sql: string): string {
  return execFileSync(
    "docker",
    ["compose", "-f", `${STAGING}/compose.yml`, "--env-file", `${STAGING}/.env`, "--env-file",
      `${STAGING}/examproctor.secrets`, "exec", "-T", "service-db", "psql", "-U", "examproctor", "-tAc", sql],
    { encoding: "utf8" },
  ).trim();
}
