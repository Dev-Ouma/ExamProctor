/** Reviewer API client. The staff token comes from Moodle's report page and covers one quiz. */

export interface Person {
  name: string;
  idnumber: string;
}

export interface AttemptLink {
  attemptid: number;
  url: string;
}

export interface DashboardConfig {
  serviceUrl: string;
  token: string;
  tokenTtl: number;
  quizId: number;
  quizName: string;
  courseName: string;
  staging: boolean;
  caps: string[];
  lang: string;
  people: Record<string, Person>;
  attempts: Record<string, AttemptLink>;
}

export type Band = "clear" | "review" | "high";

export interface SessionRow {
  session_id: string;
  moodle_user_id: number;
  status: string;
  created_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  integrity_score: number | null;
  band: Band | null;
  flag_count: number;
  uploads: Record<string, number>;
  decision: string | null;
  appeal: string | null;
  purged: boolean;
}

export interface Summary {
  sessions: number;
  finished: number;
  started: number;
  blocked: number;
  average_score: number | null;
  bands: Record<string, number>;
  decisions: Record<string, number>;
  flag_types: Record<string, number>;
}

export interface FlagItem {
  index?: number;
  type: string;
  severity: number;
  confidence: number;
  start: string;
  end: string;
  evidence: string[];
  context: Record<string, unknown>;
  question: string | null;
}

export interface Reason {
  flag_index: number;
  type: string;
  points: number;
  start: string;
  question: string | null;
}

export interface ScoreInfo {
  value: number;
  band: Band;
  reasons: Reason[];
  version: string;
  computed_at?: string;
}

export interface FaceInfo {
  box: number[];
  score: number;
  yaw: number;
}

export interface Analysis {
  faces?: FaceInfo[];
  brightness?: number;
  sharpness?: number;
  blank?: boolean;
  missing?: boolean;
}

export interface UploadItem {
  key: string;
  kind: "camera" | "screen" | "reference" | "room_scan";
  seq: number;
  captured_at: string;
  analysis: Analysis | null;
  url: string | null;
}

export interface EventItem {
  type: string;
  ts: string;
  data: Record<string, unknown>;
}

export interface ReviewItem {
  session_id: string;
  kind: "decision" | "appeal";
  value: string;
  notes: string;
  reviewer_id: number;
  reviewer_name: string;
  created_at: string;
}

export interface SessionReview {
  session: {
    session_id: string;
    moodle_user_id: number;
    status: string;
    policy: Record<string, unknown>;
    precheck: Record<string, unknown> | null;
    consent_version: string | null;
    started_at: string | null;
    ended_at: string | null;
    client_health: Record<string, unknown> | null;
    legal_hold: boolean;
    purged: boolean;
  };
  score: ScoreInfo | null;
  flags: FlagItem[];
  uploads: UploadItem[];
  events: EventItem[];
  reviews: ReviewItem[];
  url_ttl_s: number;
}

export interface LiveSession extends SessionRow {
  last_seen_at: string | null;
  online: boolean;
  paused: boolean;
  terminated: boolean;
  client_health: Record<string, unknown> | null;
  latest_camera: { url: string; captured_at: string; faces: number } | null;
  /** Face gate on identity quizzes; null when the student has not started it. */
  face_check?: { passed: boolean; override: boolean; stage: string; similarity: number | null } | null;
  recent_flags: { type: string; start: string; severity: number }[];
  actions: { id: number; type: string; reason: string; message: string; actor_name: string; created_at: string; acked_at: string | null }[];
}

export type LiveAction = "warn" | "message" | "pause" | "resume" | "terminate" | "face_override";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

export class ReviewApi {
  constructor(
    private readonly base: string,
    private readonly token: string,
    private readonly fetcher: typeof fetch = (...args) => fetch(...args),
  ) {}

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await this.fetcher(`${this.base.replace(/\/$/, "")}${path}`, {
      ...init,
      headers: { Authorization: `Bearer ${this.token}`, "Content-Type": "application/json", ...(init.headers ?? {}) },
    });
    if (!response.ok) {
      let code = "error";
      let message = response.statusText;
      try {
        const body = await response.json();
        code = body?.error?.code ?? body?.detail?.[0]?.type ?? code;
        message = body?.error?.message ?? body?.detail?.[0]?.msg ?? message;
      } catch {
        // Body was not JSON.
      }
      throw new ApiError(response.status, code, message);
    }
    return (path.endsWith(".csv") ? response.text() : response.json()) as Promise<T>;
  }

  async sessions(quizId: number): Promise<SessionRow[]> {
    const all: SessionRow[] = [];
    let after: string | null = null;
    do {
      const query: string = after ? `&after=${encodeURIComponent(after)}` : "";
      const page: { sessions: SessionRow[]; next: string | null } = await this.request(
        `/v1/review/quizzes/${quizId}/sessions?limit=200${query}`,
      );
      all.push(...page.sessions);
      after = page.next;
    } while (after);
    return all;
  }

  summary(quizId: number): Promise<Summary> {
    return this.request(`/v1/review/quizzes/${quizId}/summary`);
  }

  session(sessionId: string): Promise<SessionReview> {
    return this.request(`/v1/review/sessions/${sessionId}`);
  }

  decide(sessionId: string, decision: string, notes: string): Promise<ReviewItem> {
    return this.request(`/v1/review/sessions/${sessionId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, notes }),
    });
  }

  appeal(sessionId: string, status: string, notes: string): Promise<ReviewItem> {
    return this.request(`/v1/review/sessions/${sessionId}/appeal`, {
      method: "POST",
      body: JSON.stringify({ status, notes }),
    });
  }

  live(quizId: number): Promise<{ sessions: LiveSession[]; server_time: string }> {
    return this.request(`/v1/live/quizzes/${quizId}/sessions`);
  }

  act(sessionId: string, type: LiveAction, reason: string, message: string): Promise<unknown> {
    return this.request(`/v1/live/sessions/${sessionId}/actions`, {
      method: "POST",
      body: JSON.stringify({ type, reason, message }),
    });
  }

  /** WebSocket that says when the live wall should refresh; the token goes in the first message. */
  stream(quizId: number, onEvent: (type: string) => void, onClose: (code: number) => void): WebSocket {
    const url = `${this.base.replace(/\/$/, "").replace(/^http/, "ws")}/v1/live/quizzes/${quizId}/stream`;
    const ws = new WebSocket(url);
    ws.onopen = () => ws.send(this.token);
    ws.onmessage = (m) => {
      try {
        onEvent(JSON.parse(String(m.data)).type);
      } catch {
        // Ignore malformed frames.
      }
    };
    ws.onclose = (e) => onClose(e.code);
    return ws;
  }

  exportCsv(quizId: number): Promise<string> {
    return this.request(`/v1/review/quizzes/${quizId}/export.csv`);
  }
}
