import { describe, expect, it, vi } from "vitest";
import { ApiError, SessionApi, type SessionStatus } from "../src/api";
import type { Capabilities } from "../src/capabilities";
import { PrecheckController } from "../src/precheck";

const desktop: Capabilities = { camera: true, screen: true, indexedDb: true, isMobile: false };
const phone: Capabilities = { ...desktop, screen: false, isMobile: true };

function fakeStream(surface?: string) {
  const track = { stop: vi.fn(), getSettings: () => ({ displaySurface: surface }) };
  return { getTracks: () => [track], getVideoTracks: () => [track], track } as unknown as MediaStream & {
    track: typeof track;
  };
}

function fakeApi(policy = { camera: true, screen: true, identity: false, strict: true }) {
  const statuses: SessionStatus[] = [];
  return {
    statuses,
    exchange: vi.fn(async () => ({
      session_id: "s1",
      session_token: "t",
      policy,
      consent_text_version: "v1",
    })),
    consent: vi.fn(async () => ({ status: "consented" })),
    precheck: vi.fn(async () => statuses.shift()!),
    status: vi.fn(async () => statuses.shift()!),
  };
}

const ready = (delivered: boolean): SessionStatus => ({
  session_id: "s1",
  status: "ready",
  ready_delivered: delivered,
  reasons: [],
});

describe("PrecheckController", () => {
  it("runs the desktop flow and reports a whole-screen share", async () => {
    const api = fakeApi();
    const camera = fakeStream();
    const screen = fakeStream("monitor");
    const media = { getUserMedia: vi.fn(async () => camera), getDisplayMedia: vi.fn(async () => screen) };
    const c = new PrecheckController({ api, media, caps: desktop });
    api.statuses.push(ready(true));

    await c.start("launch");
    await c.consent();
    expect(c.pendingDevices()).toEqual(["camera", "screen"]);
    await c.requestCamera();
    await c.requestScreen();
    expect(c.pendingDevices()).toEqual([]);

    expect(await c.submit()).toEqual({ kind: "ready" });
    expect(api.consent).toHaveBeenCalledWith("v1");
    expect(api.precheck).toHaveBeenCalledWith({
      camera: "ok",
      screen: "ok",
      screen_surface: "monitor",
      screen_matches_display: null,
      network_ok: true,
    });
    // Streams stay open: the exam shell captures from them.
    expect(camera.track.stop).not.toHaveBeenCalled();
    expect(screen.track.stop).not.toHaveBeenCalled();
  });

  it("maps a refused camera to denied", async () => {
    const api = fakeApi({ camera: true, screen: false, identity: false, strict: false });
    const media = {
      getUserMedia: vi.fn(async () => {
        throw Object.assign(new Error("no"), { name: "NotAllowedError" });
      }),
    };
    const c = new PrecheckController({ api, media, caps: desktop });
    await c.start("launch");

    expect((await c.requestCamera()).status).toBe("denied");
  });

  it("reports screen as unsupported on phones without prompting", async () => {
    const api = fakeApi({ camera: true, screen: true, identity: false, strict: false });
    const getDisplayMedia = vi.fn();
    const c = new PrecheckController({
      api,
      media: { getUserMedia: async () => fakeStream(), getDisplayMedia },
      caps: phone,
    });
    await c.start("launch");
    await c.requestCamera();

    expect(c.pendingDevices()).toEqual([]);
    expect(c.results().screen).toBe("unsupported");
    expect(getDisplayMedia).not.toHaveBeenCalled();
  });

  it("polls until Moodle has received the ready webhook", async () => {
    const api = fakeApi();
    api.statuses.push(ready(false), ready(false), ready(true));
    const sleep = vi.fn(async () => undefined);
    const c = new PrecheckController({ api, media: undefined, caps: desktop, sleep, pollIntervalMs: 10 });
    await c.start("launch");

    expect(await c.submit()).toEqual({ kind: "ready" });
    expect(api.status).toHaveBeenCalledTimes(2);
  });

  it("gives up polling after the timeout", async () => {
    const api = fakeApi();
    api.statuses.push(ready(false), ready(false), ready(false), ready(false));
    const c = new PrecheckController({
      api,
      media: undefined,
      caps: desktop,
      sleep: async () => undefined,
      pollIntervalMs: 10,
      pollTimeoutMs: 20,
    });
    await c.start("launch");

    expect(await c.submit()).toEqual({ kind: "timeout" });
  });

  it("returns blocking reasons from the service", async () => {
    const api = fakeApi();
    api.statuses.push({ session_id: "s1", status: "blocked", ready_delivered: false, reasons: ["screen_not_whole_display"] });
    const c = new PrecheckController({ api, media: undefined, caps: desktop });
    await c.start("launch");

    expect(await c.submit()).toEqual({ kind: "blocked", reasons: ["screen_not_whole_display"] });
  });
});

describe("SessionApi", () => {
  it("sends the session token after exchange and raises service errors", async () => {
    const calls: [string, RequestInit][] = [];
    const responses = [
      new Response(JSON.stringify({ session_id: "s1", session_token: "tok", policy: {}, consent_text_version: "v1" })),
      new Response(JSON.stringify({ error: { code: "consent_version_mismatch", message: "reload" } }), { status: 409 }),
    ];
    const api = new SessionApi("https://svc", async (url, init) => {
      calls.push([String(url), init!]);
      return responses.shift()!;
    });

    await api.exchange("launch");
    const failure = await api.consent("old").catch((e) => e);

    expect(calls[1][0]).toBe("https://svc/v1/sessions/s1/consent");
    expect((calls[1][1].headers as Record<string, string>).Authorization).toBe("Bearer tok");
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure.code).toBe("consent_version_mismatch");
  });
});
