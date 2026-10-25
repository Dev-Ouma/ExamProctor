/** Pre-check flow: exchange -> consent -> devices -> service decision -> wait for Moodle unlock. */

import type { ExchangeResult, PrecheckResults, SessionApi, SessionStatus } from "./api";
import type { Capabilities } from "./capabilities";
import { checkCamera, checkScreen, type DeviceCheck, type MediaLike, stopStream } from "./devices";

export interface PrecheckDeps {
  api: Pick<SessionApi, "exchange" | "consent" | "precheck" | "status">;
  media: MediaLike | undefined;
  caps: Capabilities;
  sleep?: (ms: number) => Promise<void>;
  pollIntervalMs?: number;
  pollTimeoutMs?: number;
}

export type Outcome =
  | { kind: "ready" }
  | { kind: "blocked"; reasons: string[] }
  | { kind: "timeout" };

export class PrecheckController {
  session?: ExchangeResult;
  camera: DeviceCheck = { status: "not_requested" };
  screen: DeviceCheck = { status: "not_requested" };

  constructor(private readonly deps: PrecheckDeps) {}

  async start(launchToken: string): Promise<ExchangeResult> {
    this.session = await this.deps.api.exchange(launchToken);
    return this.session;
  }

  get policy() {
    if (!this.session) throw new Error("start() first");
    return this.session.policy;
  }

  async consent(): Promise<void> {
    if (!this.session) throw new Error("start() first");
    await this.deps.api.consent(this.session.consent_text_version);
  }

  async requestCamera(): Promise<DeviceCheck> {
    stopStream(this.camera.stream);
    this.camera = await checkCamera(this.deps.media);
    return this.camera;
  }

  async requestScreen(): Promise<DeviceCheck> {
    stopStream(this.screen.stream);
    this.screen = await checkScreen(this.deps.media, this.deps.caps.isMobile);
    return this.screen;
  }

  /** Devices the policy needs that have not been tried yet. */
  pendingDevices(): ("camera" | "screen")[] {
    const pending: ("camera" | "screen")[] = [];
    if (this.policy.camera && this.camera.status === "not_requested") pending.push("camera");
    if (this.policy.screen && this.screen.status === "not_requested" && !this.deps.caps.isMobile) {
      pending.push("screen");
    }
    return pending;
  }

  results(): PrecheckResults {
    const screen =
      this.policy.screen && this.deps.caps.isMobile && this.screen.status === "not_requested"
        ? "unsupported"
        : this.screen.status;
    return {
      camera: this.camera.status,
      screen,
      screen_surface: this.screen.surface ?? null,
      network_ok: true,
    };
  }

  /** Ask the service to decide, then wait until it has told Moodle. Streams are released. */
  async submit(): Promise<Outcome> {
    let status: SessionStatus = await this.deps.api.precheck(this.results());
    stopStream(this.camera.stream);
    stopStream(this.screen.stream);
    if (status.status === "blocked") return { kind: "blocked", reasons: status.reasons };
    const sleep = this.deps.sleep ?? ((ms) => new Promise((r) => setTimeout(r, ms)));
    const interval = this.deps.pollIntervalMs ?? 2000;
    let waited = 0;
    while (!status.ready_delivered) {
      if (waited >= (this.deps.pollTimeoutMs ?? 60000)) return { kind: "timeout" };
      await sleep(interval);
      waited += interval;
      status = await this.deps.api.status();
    }
    return { kind: "ready" };
  }
}
