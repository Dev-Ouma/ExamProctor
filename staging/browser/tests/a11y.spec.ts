import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { login, openQuiz, passPrechecks } from "./helpers";

// M7 accessibility checks (WCAG 2.1 AA) on ExamProctor's own UI only; Moodle's theme is out of scope.
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function audit(page: Page, selector: string, name: string) {
  const result = await new AxeBuilder({ page }).include(selector).withTags(TAGS).analyze();
  const summary = result.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.length} nodes - ${v.help} [${v.nodes.map((n) => n.target.join(" ")).join(", ")}]`);
  test.info().annotations.push({ type: name, description: summary.join("; ") || "no violations" });
  expect(summary, `${name} accessibility violations`).toEqual([]);
}

test("student pre-check, exam shell and self-view", async ({ browser }) => {
  test.setTimeout(180_000);
  const context = await browser.newContext({ permissions: ["camera"] });
  const page = await context.newPage();
  await login(page, process.env.STUDENT ?? "epstudent09");
  await openQuiz(page);
  const start = await passPrechecks(page);
  await audit(page, "#examproctor-precheck", "pre-check");
  await start.click();
  await expect(page.locator("#examproctor-selfview")).toBeVisible({ timeout: 30_000 });
  await audit(page, "#examproctor-selfview", "self-view");
  await context.close();
});

test("proctoring report: review list, session detail and live wall", async ({ page }) => {
  test.setTimeout(120_000);
  await login(page, process.env.TEACHER ?? "epteacher");
  await openQuiz(page);
  await page.goto(page.url().replace(/\/mod\/quiz\/view\.php\?id=(\d+).*/, "/local/examproctor/report.php?cmid=$1"));
  await expect(page.getByLabel("Quiz summary")).toBeVisible({ timeout: 30_000 });
  await audit(page, "#local-examproctor-review", "review list");
  await page.locator(".ep-row button").first().click();
  await expect(page.getByText(/Incident report/)).toBeVisible();
  await audit(page, "#local-examproctor-review", "session detail");
  await page.getByRole("button", { name: /All sessions/ }).click();
  await page.getByRole("tab", { name: "Live wall" }).click();
  await expect(page.getByLabel("Live wall")).toBeVisible();
  await audit(page, "#local-examproctor-review", "live wall");
});
