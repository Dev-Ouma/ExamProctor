// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { SelfView } from "../src/selfview";

const text = {
  self_view: "Your camera",
  recording: "Recording",
  screen_shared: "Screen shared",
  hide_self_view: "Hide",
  show_self_view: "Show camera",
};

function fakeStream(): MediaStream {
  const track = new EventTarget() as MediaStreamTrack;
  return { getVideoTracks: () => [track], getTracks: () => [track] } as unknown as MediaStream;
}

describe("SelfView", () => {
  it("shows the camera and a recording badge", () => {
    const view = new SelfView(text, fakeStream());
    expect(view.root.querySelector("video")).not.toBeNull();
    expect(view.root.textContent).toContain("Recording");
    expect((view.root.querySelectorAll("span")[2] as HTMLElement).hidden).toBe(true);
  });

  it("hiding keeps the recording badge visible", () => {
    const view = new SelfView(text, fakeStream(), fakeStream());
    const toggle = view.root.querySelector("button")!;
    toggle.click();
    expect(view.isHidden).toBe(true);
    expect(view.root.querySelector("video")!.hidden).toBe(true);
    expect(toggle.textContent).toBe("Show camera");
    expect(view.root.textContent).toContain("Recording");
    expect(view.root.textContent).toContain("Screen shared");
  });

  it("drops the screen badge when sharing ends", () => {
    const screen = fakeStream();
    const view = new SelfView(text, fakeStream(), screen);
    screen.getVideoTracks()[0].dispatchEvent(new Event("ended"));
    expect(view.root.textContent).toContain("Recording");
    expect((view.root.querySelectorAll("span")[2] as HTMLElement).hidden).toBe(true);
  });
});
