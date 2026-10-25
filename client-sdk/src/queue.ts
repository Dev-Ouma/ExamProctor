/** Durable upload queue. IndexedDB when available so captures survive a page reload or a crash. */

import type { UploadKind } from "./api";

export interface QueuedUpload {
  id: string; // `${kind}-${seq}`
  kind: UploadKind;
  seq: number;
  data: ArrayBuffer;
  sha256: string;
  capturedAt: string;
  attempts: number;
}

export interface UploadQueue {
  put(item: QueuedUpload): Promise<void>;
  oldest(limit: number): Promise<QueuedUpload[]>;
  remove(id: string): Promise<void>;
  size(): Promise<number>;
}

export class MemoryQueue implements UploadQueue {
  private items = new Map<string, QueuedUpload>();

  async put(item: QueuedUpload): Promise<void> {
    this.items.set(item.id, item);
  }

  async oldest(limit: number): Promise<QueuedUpload[]> {
    return [...this.items.values()].sort((a, b) => a.capturedAt.localeCompare(b.capturedAt)).slice(0, limit);
  }

  async remove(id: string): Promise<void> {
    this.items.delete(id);
  }

  async size(): Promise<number> {
    return this.items.size;
  }
}

const STORE = "uploads";

function request<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export class IndexedDbQueue implements UploadQueue {
  private constructor(private readonly db: IDBDatabase) {}

  static async open(name: string): Promise<IndexedDbQueue> {
    const req = indexedDB.open(name, 1);
    req.onupgradeneeded = () => {
      const store = req.result.createObjectStore(STORE, { keyPath: "id" });
      store.createIndex("capturedAt", "capturedAt");
    };
    return new IndexedDbQueue(await request(req));
  }

  private store(mode: IDBTransactionMode): IDBObjectStore {
    return this.db.transaction(STORE, mode).objectStore(STORE);
  }

  async put(item: QueuedUpload): Promise<void> {
    await request(this.store("readwrite").put(item));
  }

  async oldest(limit: number): Promise<QueuedUpload[]> {
    return request(this.store("readonly").index("capturedAt").getAll(null, limit));
  }

  async remove(id: string): Promise<void> {
    await request(this.store("readwrite").delete(id));
  }

  async size(): Promise<number> {
    return request(this.store("readonly").count());
  }
}

/** IndexedDB queue per session, falling back to memory (private windows, old browsers). */
export async function openQueue(sessionId: string): Promise<UploadQueue> {
  try {
    if (typeof indexedDB !== "undefined") return await IndexedDbQueue.open(`examproctor-${sessionId}`);
  } catch {
    // fall through
  }
  return new MemoryQueue();
}
