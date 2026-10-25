import { describe, expect, it } from "vitest";
import { detectCapabilities } from "../src/capabilities";

const fn = () => undefined;

describe("detectCapabilities", () => {
  it("reports camera and screen on a desktop browser", () => {
    const caps = detectCapabilities({
      navigator: {
        mediaDevices: { getUserMedia: fn, getDisplayMedia: fn },
        userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140.0",
      },
      indexedDB: {},
    });
    expect(caps).toEqual({ camera: true, screen: true, indexedDb: true, isMobile: false });
  });

  it("never offers screen capture on Android", () => {
    const caps = detectCapabilities({
      navigator: {
        mediaDevices: { getUserMedia: fn, getDisplayMedia: fn },
        userAgent: "Mozilla/5.0 (Linux; Android 14) Mobile Chrome/140.0",
      },
    });
    expect(caps.isMobile).toBe(true);
    expect(caps.screen).toBe(false);
    expect(caps.camera).toBe(true);
  });

  it("treats iPadOS with a desktop user agent as mobile", () => {
    const caps = detectCapabilities({
      navigator: {
        mediaDevices: { getUserMedia: fn },
        userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15",
        maxTouchPoints: 5,
      },
    });
    expect(caps.isMobile).toBe(true);
  });

  it("reports nothing when media APIs are missing", () => {
    expect(detectCapabilities({})).toEqual({
      camera: false,
      screen: false,
      indexedDb: false,
      isMobile: false,
    });
  });
});
