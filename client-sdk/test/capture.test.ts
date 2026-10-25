import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../src/api";
import { captureOnce, sequenceFor, sha256Hex } from "../src/capture";
import { EventCollector } from "../src/events";
import { MemoryQueue, type QueuedUpload } from "../src/queue";
import { Uploader } from "../src/uploader";

const bytes = (text: string) => new TextEncoder().encode(text).buffer as ArrayBuffer;

function item(seq: number): QueuedUpload {
  return { id: `camera-${seq}`, kind: "camera", seq, data: bytes(`frame ${seq}`), sha256: "a".repeat(64), capturedAt: new Date(1000 + seq).toISOString(), attempts: 0 };
}

function fakeApi() {
  return {
    online: true,
    puts: [] as string[],
    presign: vi.fn(async (b: { seq: number }) => ({ key: `k${b.seq}`, url: `https://s3/k${b.seq}`, headers: {} })),
    put: vi.fn(async function (this: unknown, url: string) {
      if (!api.online) throw new TypeError("Failed to fetch");
      api.puts.push(url);
    }),
    complete: vi.fn(async (key: string) => ({ key, status: "verified" })),
  };
}
let api = fakeApi();

describe("capture", () => {
  it("hashes with sha256", async () => {
    expect(await sha256Hex(bytes("abc"))).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });

  it("derives increasing sequence numbers from elapsed seconds", () => {
    expect(sequenceFor(10_000, 9_000)).toBe(0);
    expect(sequenceFor(10_000, 40_999)).toBe(30);
  });

  it("queues a frame with its hash and skips dead streams", async () => {
    const queue = new MemoryQueue();
    const live = { grab: async () => bytes("jpeg") };
    const dead = { grab: async () => null };

    expect(await captureOnce("camera", live, queue, 0, () => 5000)).toBe(true);
    expect(await captureOnce("camera", dead, queue, 0, () => 6000)).toBe(false);

    const [queued] = await queue.oldest(5);
    expect(queued.id).toBe("camera-5");
    expect(queued.sha256).toBe(await sha256Hex(bytes("jpeg")));
  });
});

describe("Uploader", () => {
  it("keeps captures through a network drop and uploads them in order afterwards", async () => {
    api = fakeApi();
    const queue = new MemoryQueue();
    const uploader = new Uploader({ api, queue });
    await queue.put(item(1));

    api.online = false;
    for (let s = 2; s <= 4; s++) await queue.put(item(s));
    expect(await uploader.drain()).toBe(0);
    expect(await uploader.drain()).toBe(0);
    expect(uploader.nextDelayMs).toBe(4000);
    expect(await queue.size()).toBe(4);

    api.online = true;
    expect(await uploader.drain()).toBe(4);
    expect(api.puts).toEqual(["https://s3/k1", "https://s3/k2", "https://s3/k3", "https://s3/k4"]);
    expect(await queue.size()).toBe(0);
    expect(uploader.nextDelayMs).toBe(1000);
  });

  it("skips the PUT when the service already has the object", async () => {
    api = fakeApi();
    api.presign.mockResolvedValueOnce({ key: "k1", already_uploaded: true } as never);
    const queue = new MemoryQueue();
    await queue.put(item(1));

    await new Uploader({ api, queue }).drain();

    expect(api.put).not.toHaveBeenCalled();
    expect(await queue.size()).toBe(0);
  });

  it("drops items the service will never accept and reports them", async () => {
    api = fakeApi();
    api.presign.mockRejectedValueOnce(new ApiError(413, "too_large", "big"));
    const queue = new MemoryQueue();
    const dropped: string[] = [];
    await queue.put(item(1));

    await new Uploader({ api, queue, onDropped: (id, code) => dropped.push(`${id}:${code}`) }).drain();

    expect(dropped).toEqual(["camera-1:too_large"]);
    expect(await queue.size()).toBe(0);
  });
});

describe("EventCollector", () => {
  it("records page events with the question id and keeps them when sending fails", async () => {
    document.body.innerHTML = '<div class="que" id="question-5-2"><p id="t">text</p></div>';
    const send = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue({ accepted: 3 });
    const events = new EventCollector({ events: send });
    events.attach(window);

    document.getElementById("t")!.dispatchEvent(new Event("paste", { bubbles: true }));
    window.dispatchEvent(new Event("blur"));

    expect(await events.flush()).toBe(0);
    expect(events.pending).toBe(3);
    expect(await events.flush()).toBe(3);
    const sent = send.mock.calls[1][0];
    expect(sent.map((e: { type: string }) => e.type)).toEqual(["question_shown", "paste", "blur"]);
    expect(sent[1].data).toEqual({ question: "question-5-2" });
    events.detachAll();
  });
});
