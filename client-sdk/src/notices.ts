/**
 * Invigilator notices in the exam shell: warnings and messages the student acknowledges, a pause
 * screen that covers the quiz until it is resumed, and the end screen after a termination.
 */

import type { Notice } from "./api";

export interface NoticeText {
  notice_warn: string;
  notice_message: string;
  notice_ok: string;
  paused: string;
  terminated: string;
}

const LAYER =
  "position:absolute;inset:0;z-index:100002;background:rgba(0,0,0,.75);display:flex;align-items:center;justify-content:center;font:16px sans-serif";
const BOX = "background:#fff;color:#000;max-width:520px;margin:16px;padding:20px;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.4)";

export class NoticeBoard {
  private pauseLayer?: HTMLElement;
  private ended = false;

  constructor(
    private readonly host: HTMLElement,
    private readonly text: NoticeText,
    private readonly ack: (id: number) => Promise<unknown>,
    private readonly onTerminate: () => void,
  ) {}

  /** Apply one heartbeat reply. */
  apply(reply: { paused?: boolean; notices?: Notice[] }): void {
    for (const notice of reply.notices ?? []) this.show(notice);
    if (!this.ended) this.setPaused(Boolean(reply.paused));
  }

  get isPaused(): boolean {
    return Boolean(this.pauseLayer);
  }

  private show(notice: Notice): void {
    if (notice.type === "terminate") {
      this.ended = true;
      this.setPaused(false);
      this.layer(this.text.terminated, notice.message);
      void this.ack(notice.id).catch(() => undefined);
      this.onTerminate();
      return;
    }
    if (notice.type === "warn" || notice.type === "message") {
      const title = notice.type === "warn" ? this.text.notice_warn : this.text.notice_message;
      const layer = this.layer(title, notice.message, true);
      const ok = document.createElement("button");
      ok.type = "button";
      ok.textContent = this.text.notice_ok;
      ok.setAttribute("style", "margin-top:12px;padding:6px 16px;font:16px sans-serif;cursor:pointer");
      ok.addEventListener("click", () => {
        layer.remove();
        void this.ack(notice.id).catch(() => undefined);
      });
      layer.firstElementChild!.append(ok);
      ok.focus();
      return;
    }
    // pause and resume arrive as state in the same reply; acknowledge that they were received.
    void this.ack(notice.id).catch(() => undefined);
  }

  private setPaused(paused: boolean): void {
    if (paused && !this.pauseLayer) {
      this.pauseLayer = this.layer(this.text.paused, "");
    } else if (!paused && this.pauseLayer) {
      this.pauseLayer.remove();
      this.pauseLayer = undefined;
    }
  }

  private layer(title: string, detail: string, dialog = false): HTMLElement {
    const layer = document.createElement("div");
    layer.className = "examproctor-notice";
    layer.setAttribute("style", LAYER);
    const box = document.createElement("div");
    box.setAttribute("role", dialog ? "alertdialog" : "alert");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("style", BOX);
    const heading = document.createElement("p");
    heading.setAttribute("style", "margin:0 0 8px;font-weight:600");
    heading.textContent = title;
    box.append(heading);
    if (detail) {
      const body = document.createElement("p");
      body.setAttribute("style", "margin:0;white-space:pre-wrap");
      body.textContent = detail;
      box.append(body);
    }
    layer.append(box);
    this.host.append(layer);
    return layer;
  }
}
