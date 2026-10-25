/** Camera and screen permission checks. Streams are stopped after the check; capture starts in M3. */

import type { DeviceStatus } from "./api";

export interface MediaLike {
  getUserMedia?: (c: MediaStreamConstraints) => Promise<MediaStream>;
  getDisplayMedia?: (c: DisplayMediaStreamOptions) => Promise<MediaStream>;
}

export interface DeviceCheck {
  status: DeviceStatus;
  stream?: MediaStream;
  surface?: string | null;
}

function classify(error: unknown): DeviceStatus {
  const name = (error as { name?: string })?.name ?? "";
  if (name === "NotAllowedError" || name === "SecurityError") return "denied";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "missing";
  return "missing";
}

export async function checkCamera(media: MediaLike | undefined): Promise<DeviceCheck> {
  if (!media?.getUserMedia) return { status: "unsupported" };
  try {
    const stream = await media.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
    return { status: "ok", stream };
  } catch (error) {
    return { status: classify(error) };
  }
}

export async function checkScreen(media: MediaLike | undefined, isMobile: boolean): Promise<DeviceCheck> {
  if (isMobile || !media?.getDisplayMedia) return { status: "unsupported" };
  try {
    const stream = await media.getDisplayMedia({
      video: { displaySurface: "monitor" } as MediaTrackConstraints,
      audio: false,
    });
    const surface = stream.getVideoTracks()[0]?.getSettings().displaySurface ?? null;
    return { status: "ok", stream, surface };
  } catch (error) {
    return { status: classify(error) };
  }
}

export function stopStream(stream?: MediaStream): void {
  stream?.getTracks().forEach((track) => track.stop());
}
