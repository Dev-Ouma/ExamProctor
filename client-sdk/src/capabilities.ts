/** Browser features the SDK needs, detected without prompting the user. */
export interface Capabilities {
  camera: boolean;
  screen: boolean;
  indexedDb: boolean;
  isMobile: boolean;
}

/** Subset of the browser globals read by detection; injectable for tests. */
export interface BrowserEnv {
  navigator?: {
    mediaDevices?: { getUserMedia?: unknown; getDisplayMedia?: unknown };
    userAgent?: string;
    maxTouchPoints?: number;
  };
  indexedDB?: unknown;
}

const MOBILE_UA = /Android|iPhone|iPad|iPod|Mobile/i;

export function detectCapabilities(env: BrowserEnv = globalThis as BrowserEnv): Capabilities {
  const media = env.navigator?.mediaDevices;
  const ua = env.navigator?.userAgent ?? "";
  // iPadOS reports a desktop Mac user agent; touch points give it away.
  const isMobile = MOBILE_UA.test(ua) || (/Macintosh/.test(ua) && (env.navigator?.maxTouchPoints ?? 0) > 1);
  return {
    camera: typeof media?.getUserMedia === "function",
    screen: !isMobile && typeof media?.getDisplayMedia === "function",
    indexedDb: env.indexedDB !== undefined,
    isMobile,
  };
}
