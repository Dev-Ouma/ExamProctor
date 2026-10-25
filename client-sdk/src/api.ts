/** Client for the ExamProctor service session API (spec section 7). */

export interface Policy {
  camera: boolean;
  screen: boolean;
  identity: boolean;
  strict: boolean;
  camera_interval_s?: number;
  screen_interval_s?: number;
}

export type UploadKind = "camera" | "screen" | "reference" | "room_scan";

export interface PresignRequest {
  kind: UploadKind;
  bytes: number;
  sha256: string;
  seq: number;
  captured_at: string;
}

export interface PresignResult {
  key: string;
  url?: string;
  headers?: Record<string, string>;
  already_uploaded?: boolean;
}

export interface ClientEvent {
  type: string;
  ts: string;
  data?: Record<string, unknown>;
}

export interface ExchangeResult {
  session_id: string;
  session_token: string;
  policy: Policy;
  consent_text_version: string;
}

export type DeviceStatus = "ok" | "denied" | "missing" | "unsupported" | "not_requested";

export interface PrecheckResults {
  camera: DeviceStatus;
  screen: DeviceStatus;
  screen_surface?: string | null;
  network_ok: boolean;
}

export interface SessionStatus {
  session_id: string;
  status: "created" | "consented" | "ready" | "blocked";
  ready_delivered: boolean;
  reasons: string[];
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

type Fetch = typeof fetch;

export class SessionApi {
  private token = "";
  private sessionId = "";

  constructor(
    private readonly baseUrl: string,
    private readonly fetchImpl: Fetch = (...args) => fetch(...args),
  ) {}

  async exchange(launchToken: string): Promise<ExchangeResult> {
    const result = await this.call<ExchangeResult>("POST", "/v1/sessions/exchange", {
      launch_token: launchToken,
    });
    this.token = result.session_token;
    this.sessionId = result.session_id;
    return result;
  }

  consent(textVersion: string): Promise<{ status: string }> {
    return this.call("POST", `/v1/sessions/${this.sessionId}/consent`, {
      text_version: textVersion,
      accepted: true,
    });
  }

  precheck(results: PrecheckResults): Promise<SessionStatus> {
    return this.call("POST", `/v1/sessions/${this.sessionId}/precheck`, results);
  }

  status(): Promise<SessionStatus> {
    return this.call("GET", `/v1/sessions/${this.sessionId}`);
  }

  presign(body: PresignRequest): Promise<PresignResult> {
    return this.call("POST", `/v1/sessions/${this.sessionId}/uploads/presign`, body);
  }

  complete(key: string): Promise<{ key: string; status: string }> {
    return this.call("POST", `/v1/sessions/${this.sessionId}/uploads/complete`, { key });
  }

  events(events: ClientEvent[]): Promise<{ accepted: number; rejected: number }> {
    return this.call("POST", `/v1/sessions/${this.sessionId}/events`, { events });
  }

  heartbeat(body: Record<string, unknown>): Promise<{ server_time: string }> {
    return this.call("POST", `/v1/sessions/${this.sessionId}/heartbeat`, body);
  }

  finish(): Promise<{ status: string }> {
    return this.call("POST", `/v1/sessions/${this.sessionId}/finish`, {});
  }

  /** PUT bytes to a presigned object-store URL. */
  async put(url: string, data: ArrayBuffer, headers: Record<string, string> = {}): Promise<void> {
    const response = await this.fetchImpl(url, { method: "PUT", body: data, headers });
    if (!response.ok) {
      throw new ApiError(response.status, "put_failed", `object store returned ${response.status}`);
    }
  }

  private async call<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.token) {
      headers.Authorization = `Bearer ${this.token}`;
    }
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const json = await response.json().catch(() => ({}));
    if (!response.ok) {
      const err = json?.error ?? {};
      throw new ApiError(response.status, err.code ?? "http_error", err.message ?? response.statusText);
    }
    return json as T;
  }
}
