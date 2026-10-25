/** Drains the upload queue: presign -> PUT -> complete, with backoff while offline. */

import { ApiError, type SessionApi } from "./api";
import type { UploadQueue } from "./queue";

/** Errors that will never succeed on retry: drop the item and report it. */
const PERMANENT = new Set(["too_large", "kind_not_in_policy", "session_purged", "seq_conflict", "bad_sha256"]);

export interface UploaderDeps {
  api: Pick<SessionApi, "presign" | "complete" | "put">;
  queue: UploadQueue;
  onDropped?: (id: string, code: string) => void;
}

export class Uploader {
  private failures = 0;

  constructor(private readonly deps: UploaderDeps) {}

  /** Delay before the next drain, in ms: 1 s when healthy, doubling to 60 s while failing. */
  get nextDelayMs(): number {
    return this.failures === 0 ? 1000 : Math.min(1000 * 2 ** this.failures, 60_000);
  }

  /** Upload what is queued. Stops at the first network failure (keeps order, avoids hammering). */
  async drain(batch = 5): Promise<number> {
    let done = 0;
    for (const item of await this.deps.queue.oldest(batch)) {
      try {
        const presigned = await this.deps.api.presign({
          kind: item.kind,
          bytes: item.data.byteLength,
          sha256: item.sha256,
          seq: item.seq,
          captured_at: item.capturedAt,
        });
        if (!presigned.already_uploaded) {
          await this.deps.api.put(presigned.url!, item.data, presigned.headers);
          await this.deps.api.complete(presigned.key);
        }
        await this.deps.queue.remove(item.id);
        done += 1;
        this.failures = 0;
      } catch (error) {
        if (error instanceof ApiError && PERMANENT.has(error.code)) {
          await this.deps.queue.remove(item.id);
          this.deps.onDropped?.(item.id, error.code);
          continue;
        }
        this.failures += 1;
        await this.deps.queue.put({ ...item, attempts: item.attempts + 1 });
        break;
      }
    }
    return done;
  }
}
