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
  /** When the browser hides displaySurface (Firefox): does the capture have the display's shape? */
  matchesDisplay?: boolean | null;
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
    const settings = stream.getVideoTracks()[0]?.getSettings() ?? {};
    const surface = settings.displaySurface ?? null;
    const matchesDisplay = surface ? null : sameShape(settings, globalThis.screen);
    return { status: "ok", stream, surface, matchesDisplay };
  } catch (error) {
    return { status: classify(error) };
  }
}

/**
 * Firefox does not report displaySurface. A whole-display capture has the display's aspect ratio
 * (resolution may be scaled); a window almost never does, because of title bars and docks.
 */
export function sameShape(
  settings: { width?: number; height?: number },
  display: { width: number; height: number } | undefined,
): boolean | null {
  if (!settings.width || !settings.height || !display?.width || !display.height) return null;
  const captured = settings.width / settings.height;
  const expected = display.width / display.height;
  return Math.abs(captured - expected) / expected < 0.02;
}

export function stopStream(stream?: MediaStream): void {
  stream?.getTracks().forEach((track) => track.stop());
}
