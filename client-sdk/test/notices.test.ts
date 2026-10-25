import { describe, expect, it, vi } from "vitest";
import { NoticeBoard } from "../src/notices";

const text = { notice_warn: "Warning", notice_message: "Message", notice_ok: "OK", paused: "Paused", terminated: "Ended" };
const at = "2026-10-25T10:00:00Z";

function board() {
  const host = document.createElement("div");
  const ack = vi.fn(async () => undefined);
  const onTerminate = vi.fn();
  return { host, ack, onTerminate, board: new NoticeBoard(host, text, ack, onTerminate) };
}

describe("NoticeBoard", () => {
  it("shows a warning until the student presses OK, then acknowledges it", () => {
    const { host, ack, board: b } = board();
    b.apply({ notices: [{ id: 7, type: "warn", message: "Please sit alone.", created_at: at }] });
    expect(host.textContent).toContain("Please sit alone.");
    expect(ack).not.toHaveBeenCalled();
    host.querySelector("button")!.click();
    expect(host.querySelector(".examproctor-notice")).toBeNull();
    expect(ack).toHaveBeenCalledWith(7);
  });

  it("covers the quiz while paused and removes the cover on resume", () => {
    const { host, board: b } = board();
    b.apply({ paused: true, notices: [{ id: 1, type: "pause", message: "Check the room", created_at: at }] });
    expect(b.isPaused).toBe(true);
    expect(host.textContent).toContain("Paused");
    b.apply({ paused: false, notices: [{ id: 2, type: "resume", message: "OK", created_at: at }] });
    expect(b.isPaused).toBe(false);
    expect(host.querySelector(".examproctor-notice")).toBeNull();
  });

  it("ends the session on terminate and stays ended", () => {
    const { host, onTerminate, board: b } = board();
    b.apply({ paused: true, notices: [{ id: 3, type: "terminate", message: "Impersonation", created_at: at }] });
    expect(onTerminate).toHaveBeenCalledOnce();
    expect(host.textContent).toContain("Ended");
    expect(b.isPaused).toBe(false);
    b.apply({ paused: true });
    expect(b.isPaused).toBe(false);
  });
});
