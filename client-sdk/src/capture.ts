/** Turns live camera/screen streams into small JPEG snapshots and queues them. */

import type { UploadKind } from "./api";
import type { UploadQueue } from "./queue";

export interface FrameSource {
  /** JPEG bytes of the current frame, or null if the stream is not live. */
  grab(): Promise<ArrayBuffer | null>;
}

export async function sha256Hex(data: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Snapshot from a MediaStream via a hidden video element and a canvas. */
export class StreamFrameSource implements FrameSource {
  private readonly video: HTMLVideoElement;

  constructor(
    private readonly stream: MediaStream,
    private readonly maxWidth: number,
    private readonly quality: number,
  ) {
    this.video = document.createElement("video");
    this.video.muted = true;
    this.video.playsInline = true;
    this.video.srcObject = stream;
    void this.video.play().catch(() => undefined);
  }

  get live(): boolean {
    return this.stream.getVideoTracks().some((t) => t.readyState === "live");
  }

  async grab(): Promise<ArrayBuffer | null> {
    if (!this.live || this.video.videoWidth === 0) return null;
    const scale = Math.min(1, this.maxWidth / this.video.videoWidth);
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(this.video.videoWidth * scale);
    canvas.height = Math.round(this.video.videoHeight * scale);
    canvas.getContext("2d")!.drawImage(this.video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, "image/jpeg", this.quality));
    return blob ? blob.arrayBuffer() : null;
  }
}

/**
 * Sequence numbers come from elapsed seconds since the session epoch, so they stay unique and
 * increasing across a shell reload without any stored counter.
 */
export function sequenceFor(epochMs: number, nowMs: number): number {
  return Math.max(0, Math.floor((nowMs - epochMs) / 1000));
}

export async function captureOnce(
  kind: UploadKind,
  source: FrameSource,
  queue: UploadQueue,
  epochMs: number,
  now: () => number = Date.now,
): Promise<boolean> {
  const data = await source.grab();
  if (!data) return false;
  const t = now();
  const seq = sequenceFor(epochMs, t);
  await queue.put({
    id: `${kind}-${seq}`,
    kind,
    seq,
    data,
    sha256: await sha256Hex(data),
    capturedAt: new Date(t).toISOString(),
    attempts: 0,
  });
  return true;
}
