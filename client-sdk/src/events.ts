/** Collects page events from the shell and the framed attempt page. Never records typed text. */

import type { ClientEvent, SessionApi } from "./api";

export class EventCollector {
  private buffer: ClientEvent[] = [];
  private readonly detachers: (() => void)[] = [];

  constructor(private readonly api: Pick<SessionApi, "events">) {}

  record(type: string, data: Record<string, unknown> = {}): void {
    this.buffer.push({ type, ts: new Date().toISOString(), data });
    if (this.buffer.length > 2000) this.buffer.splice(0, this.buffer.length - 2000);
  }

  /** Listen on a window (outer shell or the framed Moodle page). */
  attach(win: Window): void {
    const doc = win.document;
    const questionOf = (target: EventTarget | null) => {
      const el = target instanceof (win as unknown as typeof globalThis).Element ? (target as Element) : null;
      const q = el?.closest(".que");
      return q?.id ? { question: q.id } : {};
    };
    const on = <K extends keyof WindowEventMap>(target: Window | Document, type: K | string, fn: (e: Event) => void) => {
      target.addEventListener(type, fn, true);
      this.detachers.push(() => target.removeEventListener(type, fn, true));
    };
    on(win, "blur", () => this.record("blur"));
    on(win, "focus", () => this.record("focus"));
    on(doc, "visibilitychange", () => this.record(doc.hidden ? "visibility_hidden" : "visibility_visible"));
    on(doc, "fullscreenchange", () => !doc.fullscreenElement && this.record("fullscreen_exit"));
    for (const type of ["copy", "cut", "paste", "contextmenu"]) {
      on(doc, type, (e) => this.record(type, questionOf(e.target)));
    }
    on(win, "online", () => this.record("online"));
    on(win, "offline", () => this.record("offline"));
    on(win, "resize", () => this.record("resize", { w: win.innerWidth, h: win.innerHeight }));
    doc.querySelectorAll(".que[id]").forEach((q) => this.record("question_shown", { question: q.id }));
  }

  detachAll(): void {
    this.detachers.splice(0).forEach((d) => d());
  }

  /** Send buffered events. On failure they stay buffered for the next flush. */
  async flush(): Promise<number> {
    if (this.buffer.length === 0) return 0;
    const batch = this.buffer.slice(0, 500);
    try {
      await this.api.events(batch);
      this.buffer.splice(0, batch.length);
      return batch.length;
    } catch {
      return 0;
    }
  }

  get pending(): number {
    return this.buffer.length;
  }
}
