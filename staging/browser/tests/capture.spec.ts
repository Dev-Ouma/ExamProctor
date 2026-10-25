import { expect, test } from "@playwright/test";
import { login, openQuiz, passPrechecks, serviceSql } from "./helpers";

// Staging intervals (make seed): camera 10 s, screen 15 s.
test("capture runs through page changes and a 60 s network drop, then the attempt closes cleanly", async ({ page, context }) => {
  test.setTimeout(300_000);
  const student = process.env.STUDENT ?? "epstudent06";
  await login(page, student);
  await openQuiz(page);
  const start = await passPrechecks(page);
  await start.click();

  const shell = page.locator("#examproctor-shell");
  await expect(shell).toBeVisible();
  await expect(shell.getByRole("status")).toContainText("ExamProctor is on");
  const frame = page.frameLocator("#examproctor-shell iframe");
  await expect(frame.locator(".que").first()).toBeVisible({ timeout: 30_000 });

  // Page change inside the shell keeps the same capture (no new screen prompt).
  await page.waitForTimeout(20_000);
  await frame.getByRole("button", { name: /Next page/ }).click();
  await expect(frame.locator(".que").first()).toBeVisible();

  // 60 s offline: captures queue in IndexedDB, then drain.
  const offlineFrom = new Date();
  await context.setOffline(true);
  await page.waitForTimeout(60_000);
  await context.setOffline(false);
  const offlineTo = new Date();
  await page.waitForTimeout(25_000);

  // Finish the attempt inside the shell; the shell must stop and hand the top window to the review page.
  await page.evaluate(() => {
    const win = document.querySelector<HTMLIFrameElement>("#examproctor-shell iframe")!.contentWindow!;
    const params = new URL(win.location.href).searchParams;
    win.location.assign(`/mod/quiz/summary.php?attempt=${params.get("attempt")}&cmid=${params.get("cmid")}`);
  });
  await frame.getByRole("button", { name: "Submit all and finish" }).click();
  await frame.getByRole("dialog").getByRole("button", { name: "Submit all and finish" }).click();
  await expect(page).toHaveURL(/\/mod\/quiz\/review\.php/, { timeout: 30_000 });
  await expect(page.locator("#examproctor-shell")).toHaveCount(0);

  const session = serviceSql(
    "SELECT id FROM sessions WHERE status = 'finished' ORDER BY updated_at DESC LIMIT 1",
  );
  const row = (sql: string) => serviceSql(sql.replaceAll(":sid", `'${session}'`));
  expect(row("SELECT status FROM sessions WHERE id = :sid")).toBe("finished");
  const camera = Number(row("SELECT count(*) FROM uploads WHERE session_id = :sid AND kind = 'camera' AND status = 'verified'"));
  const screen = Number(row("SELECT count(*) FROM uploads WHERE session_id = :sid AND kind = 'screen' AND status = 'verified'"));
  const pending = Number(row("SELECT count(*) FROM uploads WHERE session_id = :sid AND status <> 'verified'"));
  const duringDrop = Number(
    row(`SELECT count(*) FROM uploads WHERE session_id = :sid AND status = 'verified'
         AND captured_at BETWEEN '${offlineFrom.toISOString()}' AND '${offlineTo.toISOString()}'`),
  );
  const events = row("SELECT string_agg(DISTINCT type, ',' ORDER BY type) FROM events WHERE session_id = :sid");
  test.info().annotations.push({ type: "evidence", description: `camera=${camera} screen=${screen} drop=${duringDrop} events=${events}` });

  expect(camera).toBeGreaterThanOrEqual(9); // ~110 s at 10 s
  expect(screen).toBeGreaterThanOrEqual(5); // ~110 s at 15 s
  expect(duringDrop).toBeGreaterThanOrEqual(6); // captured while offline, uploaded after
  expect(pending).toBe(0);
  expect(events).toContain("offline");
  expect(events).toContain("online");
  expect(events).toContain("attempt_left");
});
