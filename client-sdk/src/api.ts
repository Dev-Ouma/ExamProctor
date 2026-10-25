/** Client for the ExamProctor service session API (spec section 7). */

export interface Policy {
  camera: boolean;
  screen: boolean;
  identity: boolean;
  strict: boolean;
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
