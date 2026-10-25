import { expect, test } from "@playwright/test";
import { login, openQuiz, passPrechecks } from "./helpers";

// End to end on a deployed site: a student sits the quiz with fake camera and screen, then a
// teacher opens the proctoring report, plays the evidence back and records a decision.
// Run: MOODLE_URL=https://... SEED_USER_PASSWORD=... SHOTS=/some/dir npx playwright test review.spec.ts
const shots = process.env.SHOTS;
const shot = (name: string) => (shots ? { path: `${shots}/${name}.png`, fullPage: true } : undefined);

test("student evidence reaches the teacher's proctoring report", async ({ browser }) => {
  test.setTimeout(300_000);
  const studentContext = await browser.newContext({ permissions: ["camera"], viewport: { width: 1366, height: 900 } });
  const page = await studentContext.newPage();
  await login(page, process.env.STUDENT ?? "epstudent05");
  await openQuiz(page);
  const start = await passPrechecks(page);
  await page.screenshot(shot("1-precheck-self-view"));
  await start.click();

  const shell = page.locator("#examproctor-shell");
  await expect(shell.getByRole("status")).toContainText("ExamProctor is on");
  await expect(page.locator("#examproctor-selfview video")).toBeVisible();
  await expect(page.locator("#examproctor-selfview")).toContainText("Recording");
  const frame = page.frameLocator("#examproctor-shell iframe");
  await expect(frame.locator(".que").first()).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(15_000);
  await page.screenshot(shot("2-exam-self-view"));
  // A focus change the report should show.
  await page.evaluate(() => window.dispatchEvent(new Event("blur")));
  await page.waitForTimeout(25_000);
  await page.evaluate(() => {
    const win = document.querySelector<HTMLIFrameElement>("#examproctor-shell iframe")!.contentWindow!;
    const params = new URL(win.location.href).searchParams;
    win.location.assign(`/mod/quiz/summary.php?attempt=${params.get("attempt")}&cmid=${params.get("cmid")}`);
  });
  await frame.getByRole("button", { name: "Submit all and finish" }).click();
  await frame.getByRole("dialog").getByRole("button", { name: "Submit all and finish" }).click();
  await expect(page).toHaveURL(/\/mod\/quiz\/review\.php/, { timeout: 30_000 });
  const cmid = new URL(page.url()).searchParams.get("cmid");
  await studentContext.close();

  // Give the worker time to analyse and score.
  await new Promise((r) => setTimeout(r, 20_000));

  const teacherContext = await browser.newContext({ viewport: { width: 1366, height: 1000 } });
  const teacher = await teacherContext.newPage();
  await login(teacher, process.env.TEACHER ?? "epteacher");
  await openQuiz(teacher);
  // Moodle's secondary navigation puts extra quiz pages under "More".
  await teacher.getByRole("menuitem", { name: /More/ }).click();
  await teacher.getByRole("menuitem", { name: "Proctoring report" }).click();
  await expect(teacher.getByText("Sessions").first()).toBeVisible({ timeout: 30_000 });
  await teacher.screenshot(shot("3-report-list"));
  await teacher.getByRole("button", { name: /Synthetic Student 05/ }).first().click();
  await expect(teacher.getByText(/Incident report/)).toBeVisible();
  const camera = teacher.getByAltText(/Camera snapshot/);
  await expect(camera).toBeVisible();
  await expect.poll(() => camera.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
  await expect(teacher.getByAltText(/Screen snapshot/)).toBeVisible();
  await teacher.screenshot(shot("4-session-playback"));
  await teacher.getByRole("button", { name: "Play" }).click();
  await teacher.waitForTimeout(3_000);
  await teacher.getByLabel("Record a decision", { exact: true }).selectOption("no_issue");
  await teacher.getByLabel("Record a decision: notes").fill("Automated end-to-end check: synthetic student.");
  await teacher.locator(".ep-form").first().getByRole("button", { name: "Save" }).click();
  await expect(teacher.getByText("Saved.").first()).toBeVisible();
  await expect(teacher.locator(".ep-history")).toContainText("No issue");
  await teacher.screenshot(shot("5-decision-recorded"));
  expect(cmid).not.toBeNull();
  await teacherContext.close();
});

// Fast check of the teacher side alone, against sessions already on the site.
test("teacher opens the proctoring report from the quiz menu", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1366, height: 1000 } });
  const teacher = await context.newPage();
  await login(teacher, process.env.TEACHER ?? "epteacher");
  await openQuiz(teacher);
  await teacher.getByRole("menuitem", { name: /More/ }).click();
  await teacher.getByRole("menuitem", { name: "Proctoring report" }).click();
  await expect(teacher.getByLabel("Quiz summary")).toBeVisible({ timeout: 30_000 });
  await context.close();
});
