import { expect, test } from "@playwright/test";
import { login, openQuiz, passPrechecks } from "./helpers";

// M6 end to end: an invigilator warns, pauses, resumes and ends a live session; the student sees
// each step and Moodle closes the attempt. Run against a deployed site (see review.spec.ts).
const shots = process.env.SHOTS;
const shot = (name: string) => (shots ? { path: `${shots}/${name}.png` } : undefined);

test("invigilator actions reach the student", async ({ browser }) => {
  test.setTimeout(300_000);
  const studentContext = await browser.newContext({ permissions: ["camera"], viewport: { width: 1366, height: 900 } });
  const student = await studentContext.newPage();
  const name = process.env.STUDENT ?? "epstudent07";
  await login(student, name);
  await openQuiz(student);
  await (await passPrechecks(student)).click();
  await expect(student.locator("#examproctor-shell").getByRole("status").first()).toContainText("ExamProctor is on");
  await student.waitForTimeout(12_000);

  const staffContext = await browser.newContext({ viewport: { width: 1366, height: 1000 } });
  const staff = await staffContext.newPage();
  await login(staff, process.env.INVIGILATOR ?? "epinvigilator");
  await openQuiz(staff);
  await staff.getByRole("menuitem", { name: /More/ }).click();
  await staff.getByRole("menuitem", { name: "Proctoring report" }).click();
  const liveTab = staff.getByRole("tab", { name: "Live wall" });
  if (await liveTab.isVisible().catch(() => false)) await liveTab.click();
  // Ended sessions stay on the wall for 10 minutes; pick this run's card by its session state.
  const card = staff.getByRole("article", { name: new RegExp(`Synthetic Student ${name.slice(-2)}`) }).filter({ hasNotText: /Ended by invigilator|Finished/ }).first();
  await expect(card.getByText("Online")).toBeVisible({ timeout: 30_000 });
  await expect(staff.getByText("live updates on")).toBeVisible({ timeout: 15_000 });
  await expect(staff.locator(".alert-danger")).toHaveCount(0);
  await staff.screenshot(shot("7-live-wall"));

  const send = async (action: string, reason: string, message?: string, confirm = false) => {
    await card.getByRole("button", { name: action, exact: true }).click();
    await card.getByLabel(`${action}: reason`).fill(reason);
    if (message) await card.getByLabel(`${action}: message to student`).fill(message);
    if (confirm) await card.getByRole("checkbox").check();
    await card.getByRole("button", { name: `Send ${action.toLowerCase()}` }).click();
    await expect(card.getByText(`${action} sent.`)).toBeVisible();
  };

  await send("Warn", "Looking at another screen", "Please keep your eyes on the quiz.");
  const warning = student.getByRole("alertdialog");
  await expect(warning).toContainText("Please keep your eyes on the quiz.", { timeout: 20_000 });
  await student.screenshot(shot("8-student-warning"));
  await warning.getByRole("button", { name: "OK" }).click();

  await send("Pause", "Checking the room");
  await expect(student.getByRole("alert").filter({ hasText: "paused your exam" })).toBeVisible({ timeout: 20_000 });
  await student.screenshot(shot("9-student-paused"));
  await send("Resume", "Room is clear");
  await expect(student.getByRole("alert").filter({ hasText: "paused your exam" })).toHaveCount(0, { timeout: 20_000 });

  await send("End session", "End-to-end test of termination", undefined, true);
  await expect(student.getByRole("alert").filter({ hasText: "ended your exam session" })).toBeVisible({ timeout: 20_000 });
  await student.screenshot(shot("10-student-ended"));
  await expect(staff.getByText("Ended by invigilator").first()).toBeVisible({ timeout: 30_000 });
  // Moodle closed the attempt: after the reload the quiz page shows no attempt in progress.
  await expect(student.locator("#examproctor-shell")).toHaveCount(0, { timeout: 30_000 });
  await expect(student.getByRole("button", { name: /Continue your attempt/i })).toHaveCount(0);
  await studentContext.close();
  await staffContext.close();
});
