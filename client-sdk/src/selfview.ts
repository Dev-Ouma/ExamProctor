/**
 * Self-view: the student sees what the camera sees and that capture is on. Hiding the panel only
 * hides the picture; capture continues and the recording badge stays visible.
 */

export interface SelfViewText {
  self_view: string;
  recording: string;
  screen_shared: string;
  hide_self_view: string;
  show_self_view: string;
}

/** A muted, mirrored, inline video of a camera stream. */
export function previewVideo(stream: MediaStream, width: number): HTMLVideoElement {
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.autoplay = true;
  video.srcObject = stream;
  video.setAttribute("aria-hidden", "true");
  video.setAttribute("style", `width:${width}px;max-width:100%;transform:scaleX(-1);border-radius:6px;background:#000;display:block`);
  // Older engines return undefined rather than a promise.
  void Promise.resolve(video.play()).catch(() => undefined);
  return video;
}

export class SelfView {
  readonly root: HTMLElement;
  private readonly video?: HTMLVideoElement;
  private readonly screenBadge: HTMLElement;
  private readonly toggle: HTMLButtonElement;
  private hidden = false;

  constructor(
    private readonly text: SelfViewText,
    camera?: MediaStream,
    screen?: MediaStream,
  ) {
    this.root = document.createElement("div");
    this.root.id = "examproctor-selfview";
    this.root.setAttribute("role", "region");
    this.root.setAttribute("aria-label", text.self_view);
    this.root.setAttribute(
      "style",
      "position:fixed;right:12px;bottom:12px;z-index:100001;background:#111;color:#fff;padding:6px;" +
        "border-radius:8px;font:12px sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.4);max-width:45vw",
    );
    const bar = document.createElement("div");
    bar.setAttribute("style", "display:flex;align-items:center;gap:6px;margin-bottom:4px");
    const rec = document.createElement("span");
    rec.innerHTML = '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#e53935;margin-right:4px"></span>';
    rec.append(text.recording);
    this.screenBadge = document.createElement("span");
    this.screenBadge.textContent = text.screen_shared;
    this.screenBadge.setAttribute("style", "background:#037b90;border-radius:4px;padding:0 4px");
    this.screenBadge.hidden = !screen;
    this.toggle = document.createElement("button");
    this.toggle.type = "button";
    this.toggle.textContent = text.hide_self_view;
    this.toggle.setAttribute("style", "margin-left:auto;font:12px sans-serif;background:#333;color:#fff;border:0;border-radius:4px;padding:2px 6px;cursor:pointer");
    this.toggle.addEventListener("click", () => this.setHidden(!this.hidden));
    bar.append(rec, this.screenBadge, this.toggle);
    this.root.append(bar);
    if (camera) {
      this.video = previewVideo(camera, 180);
      this.root.append(this.video);
    } else {
      this.toggle.hidden = true;
    }
    screen?.getVideoTracks().forEach((track) => track.addEventListener("ended", () => (this.screenBadge.hidden = true)));
  }

  setHidden(hidden: boolean): void {
    this.hidden = hidden;
    if (this.video) this.video.hidden = hidden;
    this.toggle.textContent = hidden ? this.text.show_self_view : this.text.hide_self_view;
  }

  get isHidden(): boolean {
    return this.hidden;
  }
}
