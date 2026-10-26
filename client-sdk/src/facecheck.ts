/** Face check loop: sends camera frames until the service says the check passed, or time runs out. */

import type { FaceCheck } from "./api";

export interface FaceCheckDeps {
  grab: () => Promise<ArrayBuffer | null>;
  check: (jpeg: ArrayBuffer) => Promise<FaceCheck>;
  onResult: (result: FaceCheck) => void;
  sleep?: (ms: number) => Promise<void>;
  intervalMs?: number;
  timeoutMs?: number;
}

const UNREADABLE: FaceCheck = {
  ok: false,
  gated: false,
  reason: "unreadable",
  next: "hold_still",
  reference: "none",
  faces: 0,
  face_px: 0,
  brightness: 0,
};

/** Advisory checks stop after one frame; gated checks keep going so the student can follow the steps. */
export async function runFaceCheck(deps: FaceCheckDeps): Promise<FaceCheck> {
  const sleep = deps.sleep ?? ((ms) => new Promise<void>((r) => window.setTimeout(r, ms)));
  const interval = deps.intervalMs ?? 700;
  const deadline = deps.timeoutMs ?? 45000;
  let waited = 0;
  for (;;) {
    const frame = await deps.grab();
    const result = frame ? await deps.check(frame) : UNREADABLE;
    deps.onResult(result);
    // An unreadable frame (camera still starting) is retried; the service has not seen it.
    if (result.ok || (frame && !result.gated) || waited >= deadline) return result;
    await sleep(interval);
    waited += interval;
  }
}
