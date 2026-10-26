import { describe, expect, it } from "vitest";
import type { FaceCheck } from "../src/api";
import { runFaceCheck } from "../src/facecheck";

const base: FaceCheck = {
  ok: false,
  gated: true,
  reason: null,
  next: "hold_still",
  reference: "institutional",
  faces: 1,
  face_px: 160,
  brightness: 120,
};

function scripted(results: Partial<FaceCheck>[]) {
  const seen: FaceCheck[] = [];
  let sent = 0;
  const deps = {
    grab: async () => new ArrayBuffer(4),
    check: async () => ({ ...base, ...results[Math.min(sent++, results.length - 1)] }),
    onResult: (r: FaceCheck) => seen.push(r),
    sleep: async () => {},
  };
  return { deps, seen, sent: () => sent };
}

describe("runFaceCheck", () => {
  it("keeps sending frames through the steps until the gate passes", async () => {
    const s = scripted([{}, {}, { next: "turn_left" }, { next: "look_back" }, { ok: true, next: "done" }]);
    const result = await runFaceCheck(s.deps);
    expect(result.ok).toBe(true);
    expect(s.seen.map((r) => r.next)).toEqual(["hold_still", "hold_still", "turn_left", "look_back", "done"]);
  });

  it("stops after one frame when the check is advisory", async () => {
    const s = scripted([{ gated: false, reason: "too_dark" }]);
    await runFaceCheck(s.deps);
    expect(s.sent()).toBe(1);
  });

  it("gives up at the timeout so the student can ask for help", async () => {
    const s = scripted([{ reason: "not_same_person" }]);
    const result = await runFaceCheck({ ...s.deps, intervalMs: 1000, timeoutMs: 3000 });
    expect(result.ok).toBe(false);
    expect(s.sent()).toBe(4);
  });

  it("reports an unreadable frame without calling the service", async () => {
    const s = scripted([{}]);
    const result = await runFaceCheck({ ...s.deps, grab: async () => null, timeoutMs: 0 });
    expect(result.reason).toBe("unreadable");
    expect(s.sent()).toBe(0);
  });
});
