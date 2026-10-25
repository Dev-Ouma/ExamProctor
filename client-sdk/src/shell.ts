/**
 * Exam shell: a persistent same-origin page that frames the Moodle attempt so camera and screen
 * streams survive page loads with a single permission prompt (spec 5.2, requirement R3).
 */

import type { Policy, SessionApi } from "./api";
import { captureOnce, type FrameSource, StreamFrameSource } from "./capture";
import { EventCollector } from "./events";
import { NoticeBoard, type NoticeText } from "./notices";
import { SelfView, type SelfViewText } from "./selfview";
import type { UploadQueue } from "./queue";
import { Uploader } from "./uploader";

const ATTEMPT_PAGES = /\/mod\/quiz\/(attempt|summary|startattempt|processattempt)\.php$/;

export interface ShellDeps {
  api: Pick<SessionApi, "presign" | "complete" | "put" | "events" | "heartbeat" | "finish" | "ack">;
  policy: Policy;
  queue: UploadQueue;
  camera?: MediaStream;
  screen?: MediaStream;
  staging: boolean;
  text: { capturing: string; screenStopped: string; leaving: string; reconnecting: string } & SelfViewText & NoticeText;
}

export class ExamShell {
  readonly events: EventCollector;
  private readonly uploader: Uploader;
  private readonly timers: number[] = [];
  private readonly epoch = Date.now();
  private iframe?: HTMLIFrameElement;
  private status?: HTMLElement;
  private stopped = false;
  private lastGoodUrl?: string;
  private frameBroken = false;
  private selfView?: SelfView;
  private notices?: NoticeBoard;

  constructor(private readonly deps: ShellDeps) {
    this.events = new EventCollector(deps.api);
    this.uploader = new Uploader({
      api: deps.api,
      queue: deps.queue,
      onDropped: (id, code) => this.events.record("capture_error", { id, code }),
    });
  }

  /** Submit the (already validated) preflight form into the shell frame and start capture. */
  start(form: HTMLFormElement): void {
    const name = "examproctor-shell-frame";
    const overlay = document.createElement("div");
    overlay.id = "examproctor-shell";
    overlay.setAttribute("style", "position:fixed;inset:0;z-index:100000;background:#fff;display:flex;flex-direction:column");
    this.status = document.createElement("div");
    this.status.setAttribute("role", "status");
    this.status.setAttribute("style", `padding:4px 12px;font:14px sans-serif;background:${this.deps.staging ? "#ff7f50" : "#037b90"};color:#fff`);
    this.status.textContent = this.deps.text.capturing;
    this.iframe = document.createElement("iframe");
    this.iframe.name = name;
    this.iframe.title = "Quiz";
    this.iframe.setAttribute("style", "flex:1;border:0;width:100%");
    overlay.append(this.status, this.iframe);
    this.selfView = new SelfView(this.deps.text, this.deps.camera, this.deps.screen);
    overlay.append(this.selfView.root);
    this.notices = new NoticeBoard(overlay, this.deps.text, (id) => this.deps.api.ack(id), () => {
      this.events.record("terminated_by_invigilator");
      // Moodle closes the attempt; reload the quiz page once capture has stopped.
      void this.stop().finally(() => window.setTimeout(() => window.location.reload(), 8000));
    });
    document.body.append(overlay);
    this.iframe.addEventListener("load", () => this.onFrameLoad());

    form.target = name;
    HTMLFormElement.prototype.submit.call(form); // bypasses submit listeners

    this.events.attach(window);
    this.events.record("shell_loaded");
    // Chromium exposes whether the desktop spans more than one display (no permission prompt).
    const extended = (window.screen as Screen & { isExtended?: boolean }).isExtended;
    if (extended !== undefined) this.events.record("display_info", { extended });
    this.watchStream(this.deps.screen, "screen");
    this.watchStream(this.deps.camera, "camera");
    this.startLoops();
  }

  private watchStream(stream: MediaStream | undefined, kind: string): void {
    stream?.getVideoTracks().forEach((track) =>
      track.addEventListener("ended", () => {
        this.events.record("stream_ended", { kind });
        if (kind === "screen" && this.status) this.status.textContent = this.deps.text.screenStopped;
      }),
    );
  }

  private onFrameLoad(): void {
    const win = this.iframe?.contentWindow;
    if (!win) return;
    let href: string;
    try {
      href = win.location.href; // throws on a browser error page (offline) or a foreign redirect
    } catch {
      this.frameBroken = true;
      this.events.record("connectivity_gap", { frame: "unreadable" });
      if (this.status) this.status.textContent = this.deps.text.reconnecting;
      return;
    }
    if (ATTEMPT_PAGES.test(new URL(href).pathname)) {
      this.frameBroken = false;
      this.lastGoodUrl = href;
      if (this.status) this.status.textContent = this.deps.text.capturing;
      this.events.attach(win);
      return;
    }
    // Left the attempt (submitted, timed out, review page, quiz home): stop and go there for real.
    this.events.record("attempt_left", { path: new URL(href).pathname });
    if (this.status) this.status.textContent = this.deps.text.leaving;
    void this.stop().finally(() => window.location.assign(href));
  }

  private every(ms: number, fn: () => unknown): void {
    this.timers.push(window.setInterval(() => void fn(), ms));
  }

  private startLoops(): void {
    const sources: [("camera" | "screen"), FrameSource, number][] = [];
    if (this.deps.camera) {
      sources.push(["camera", new StreamFrameSource(this.deps.camera, 640, 0.6), this.deps.policy.camera_interval_s ?? 30]);
    }
    if (this.deps.screen) {
      sources.push(["screen", new StreamFrameSource(this.deps.screen, 1280, 0.5), this.deps.policy.screen_interval_s ?? 60]);
    }
    if (this.deps.policy.identity && sources[0]?.[0] === "camera") {
      // Live reference frame for identity matching when no institutional photo exists.
      const camera = sources[0][1];
      window.setTimeout(() => void captureOnce("reference", camera, this.deps.queue, this.epoch - 1000), 1500);
    }
    for (const [kind, source, seconds] of sources) {
      this.every(seconds * 1000, () => captureOnce(kind, source, this.deps.queue, this.epoch));
    }
    const drain = async () => {
      if (this.stopped) return;
      await this.uploader.drain();
      this.timers.push(window.setTimeout(drain, this.uploader.nextDelayMs));
    };
    void drain();
    this.every(5000, () => this.events.flush());
    // After a connection drop the frame may show a browser error page; reload the last attempt page.
    const recover = () => {
      if (this.frameBroken && navigator.onLine && this.iframe && this.lastGoodUrl) {
        this.frameBroken = false;
        this.iframe.src = this.lastGoodUrl;
      }
    };
    window.addEventListener("online", recover);
    this.every(5000, recover);
    const beat = async () =>
      this.deps.api
        .heartbeat({
          queued_uploads: await this.deps.queue.size(),
          camera_live: this.deps.camera?.getVideoTracks().some((t) => t.readyState === "live") ?? null,
          screen_live: this.deps.screen?.getVideoTracks().some((t) => t.readyState === "live") ?? null,
        })
        .then((reply) => this.notices?.apply(reply))
        .catch(() => this.events.record("connectivity_gap"));
    void beat();
    this.every(10000, beat);
  }

  /** Stop capture, try to send what is queued (up to 10 s), close the session, release devices. */
  async stop(): Promise<void> {
    if (this.stopped) return;
    this.stopped = true;
    this.timers.splice(0).forEach((t) => {
      clearInterval(t);
      clearTimeout(t);
    });
    const deadline = Date.now() + 10_000;
    while (Date.now() < deadline && (await this.deps.queue.size()) > 0) {
      if ((await this.uploader.drain(10)) === 0) break;
    }
    await this.events.flush();
    await this.deps.api.finish().catch(() => undefined);
    this.events.detachAll();
    this.selfView?.root.remove();
    [this.deps.camera, this.deps.screen].forEach((s) => s?.getTracks().forEach((t) => t.stop()));
  }
}
