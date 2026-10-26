import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { type DashboardConfig, ReviewApi } from "../src/api";
import { App, StagingBanner } from "../src/App";
import { nearestBefore } from "../src/Player";

const config: DashboardConfig = {
  serviceUrl: "https://svc.example/api",
  token: "staff-token",
  tokenTtl: 3600,
  quizId: 3,
  quizName: "Practice quiz",
  courseName: "Course 101",
  staging: true,
  caps: ["review", "decide", "exportevidence"],
  lang: "en",
  people: { "42": { name: "Synthetic Student", idnumber: "OUK-001" }, "43": { name: "Other Student", idnumber: "" } },
  attempts: {},
};

const sessions = [
  {
    session_id: "s1",
    moodle_user_id: 42,
    status: "ready",
    created_at: null,
    started_at: "2026-10-25T10:00:00Z",
    ended_at: "2026-10-25T10:10:00Z",
    integrity_score: 62,
    band: "review",
    flag_count: 2,
    uploads: { camera: 2, screen: 1 },
    decision: null,
    appeal: null,
    purged: false,
  },
  {
    session_id: "s2",
    moodle_user_id: 43,
    status: "ready",
    created_at: null,
    started_at: "2026-10-25T10:01:00Z",
    ended_at: "2026-10-25T10:09:00Z",
    integrity_score: 97,
    band: "clear",
    flag_count: 0,
    uploads: { camera: 3 },
    decision: "no_issue",
    appeal: null,
    purged: false,
  },
];

const review = {
  session: {
    session_id: "s1",
    moodle_user_id: 42,
    status: "ready",
    policy: { camera: true },
    precheck: { camera: "ok", network: "slow" },
    consent_version: "v1",
    started_at: "2026-10-25T10:00:00Z",
    ended_at: "2026-10-25T10:10:00Z",
    client_health: null,
    legal_hold: false,
    purged: false,
  },
  score: { value: 62, band: "review", reasons: [{ flag_index: 0, type: "NO_FACE", points: 20, start: "2026-10-25T10:02:00Z", question: null }], version: "v1" },
  flags: [
    { index: 0, type: "NO_FACE", severity: 3, confidence: 0.9, start: "2026-10-25T10:02:00Z", end: "2026-10-25T10:03:00Z", evidence: ["k1"], context: {}, question: null },
  ],
  uploads: [
    { key: "k1", kind: "camera", seq: 0, captured_at: "2026-10-25T10:01:00Z", analysis: { faces: [] }, url: "https://img/1.jpg" },
    { key: "k2", kind: "camera", seq: 1, captured_at: "2026-10-25T10:02:00Z", analysis: { faces: [] }, url: "https://img/2.jpg" },
    { key: "k3", kind: "screen", seq: 0, captured_at: "2026-10-25T10:01:30Z", analysis: null, url: "https://img/3.jpg" },
  ],
  events: [{ type: "blur", ts: "2026-10-25T10:02:10Z", data: {} }],
  reviews: [],
  url_ttl_s: 600,
};

function fakeFetch() {
  const calls: { url: string; init?: RequestInit }[] = [];
  const fetcher = async (url: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    const path = String(url).replace(config.serviceUrl, "");
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
    if (path.startsWith("/v1/review/quizzes/3/sessions")) return json({ sessions, next: null });
    if (path === "/v1/review/quizzes/3/summary")
      return json({ sessions: 2, finished: 2, started: 2, blocked: 0, average_score: 79.5, bands: { review: 1, clear: 1 }, decisions: { undecided: 1, no_issue: 1 }, flag_types: { NO_FACE: 1 } });
    if (path === "/v1/review/sessions/s1") return json(review);
    if (path === "/v1/review/sessions/s1/decision") return json({ ...JSON.parse(String(init?.body)), kind: "decision" });
    return json({ error: { code: "not_found", message: "nope" } }, 404);
  };
  return { calls, api: new ReviewApi(config.serviceUrl, config.token, fetcher as typeof fetch) };
}

describe("StagingBanner", () => {
  it("shows in staging and hides in live", () => {
    const { rerender } = render(<StagingBanner mode="staging" />);
    expect(screen.getByRole("status").textContent).toContain("Staging");
    rerender(<StagingBanner mode="live" />);
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("App", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("lists sessions lowest score first with names from Moodle and sends the staff token", async () => {
    const { api, calls } = fakeFetch();
    render(<App config={config} api={api} />);
    await screen.findByText("Synthetic Student");
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0].textContent).toContain("Synthetic Student");
    expect(rows[1].textContent).toContain("Other Student");
    expect(screen.getByText("Average score").previousSibling?.textContent).toBe("80");
    expect((calls[0].init?.headers as Record<string, string>).Authorization).toBe("Bearer staff-token");
  });

  it("filters by band", async () => {
    const { api } = fakeFetch();
    render(<App config={config} api={api} />);
    await screen.findByText("Synthetic Student");
    fireEvent.change(screen.getByLabelText("Filter by band"), { target: { value: "clear" } });
    expect(screen.queryByText("Synthetic Student")).toBeNull();
    expect(screen.getByText("Other Student")).toBeTruthy();
  });

  it("opens a session with playback, flags and a decision form", async () => {
    const { api, calls } = fakeFetch();
    render(<App config={config} api={api} />);
    fireEvent.click(await screen.findByText("Synthetic Student"));
    await screen.findByText(/Incident report/);
    expect(screen.getAllByText("No face in camera view").length).toBeGreaterThan(0);
    expect(screen.getByAltText(/Camera snapshot/)).toBeTruthy();
    expect(screen.getByAltText(/Screen snapshot/)).toBeTruthy();
    expect(screen.getByText(/network: slow/)).toBeTruthy();

    const decision = screen.getByLabelText("Record a decision");
    fireEvent.change(decision, { target: { value: "concern" } });
    const save = screen.getAllByText("Save")[0] as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Record a decision: notes"), { target: { value: "Face missing for a minute." } });
    fireEvent.click(save);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/v1/review/sessions/s1/decision"))).toBe(true));
    const sent = calls.find((c) => c.url.endsWith("/decision"))!;
    expect(JSON.parse(String(sent.init?.body))).toEqual({ decision: "concern", notes: "Face missing for a minute." });
  });

  it("shows the service error", async () => {
    const api = new ReviewApi(config.serviceUrl, config.token, (async () =>
      new Response(JSON.stringify({ error: { code: "unauthorized", message: "invalid staff token" } }), { status: 401 })) as typeof fetch);
    render(<App config={config} api={api} />);
    await screen.findByText(/invalid staff token/);
    expect(screen.getByText(/access has expired/)).toBeTruthy();
  });
});

describe("nearestBefore", () => {
  const items = [{ t: 10 }, { t: 20 }, { t: 30 }];
  it("picks the last item at or before the time", () => {
    expect(nearestBefore(items, 25)?.t).toBe(20);
    expect(nearestBefore(items, 30)?.t).toBe(30);
  });
  it("falls back to the first item", () => {
    expect(nearestBefore(items, 5)?.t).toBe(10);
  });
});

describe("Live wall", () => {
  const live = {
    ...sessions[0],
    ended_at: null,
    last_seen_at: "2026-10-25T10:05:00Z",
    online: true,
    paused: false,
    terminated: false,
    client_health: { queued_uploads: 0 },
    latest_camera: { url: "https://img/live.jpg", captured_at: "2026-10-25T10:05:00Z", faces: 1 },
    recent_flags: [{ type: "MULTIPLE_FACES", start: "2026-10-25T10:04:00Z", severity: 3 }],
    actions: [],
  };

  function liveApi() {
    const calls: { url: string; body?: string }[] = [];
    const fetcher = async (url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(url), body: init?.body ? String(init.body) : undefined });
      const path = String(url).replace(config.serviceUrl, "");
      if (path === "/v1/live/quizzes/3/sessions") return new Response(JSON.stringify({ sessions: [live], server_time: "2026-10-25T10:05:05Z" }));
      if (path.endsWith("/actions")) return new Response(JSON.stringify({ id: 1 }));
      return new Response(JSON.stringify({ sessions: [], next: null, bands: {}, decisions: {}, flag_types: {} }));
    };
    return { calls, api: new ReviewApi(config.serviceUrl, config.token, fetcher as typeof fetch) };
  }

  it("shows online students and sends a warning with a reason", async () => {
    const { api, calls } = liveApi();
    render(<App config={{ ...config, caps: ["review", "decide", "invigilate"] }} api={api} />);
    fireEvent.click(screen.getByRole("tab", { name: "Live wall" }));
    await screen.findByText("Online");
    expect(screen.getByText(/More than one face in view/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Warn" }));
    const send = screen.getByRole("button", { name: "Send warn" }) as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Warn: reason"), { target: { value: "Second person behind" } });
    fireEvent.click(send);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/v1/live/sessions/s1/actions"))).toBe(true));
    const sent = calls.find((c) => c.url.endsWith("/actions"))!;
    expect(JSON.parse(sent.body!)).toEqual({ type: "warn", reason: "Second person behind", message: "" });
  });

  it("needs a confirmation before ending a session", async () => {
    const { api } = liveApi();
    render(<App config={{ ...config, caps: ["invigilate"] }} api={api} />);
    await screen.findByText("Online");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(document.querySelector(".alert-danger")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "End session" }));
    fireEvent.change(screen.getByLabelText("End session: reason"), { target: { value: "Impersonation" } });
    const send = screen.getByRole("button", { name: "Send end session" }) as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(send.disabled).toBe(false);
  });

  it("lets an invigilator admit a student held at the face check, with a reason", async () => {
    const held = { ...live, started_at: null, status: "blocked", latest_camera: null, recent_flags: [] };
    const { calls } = liveApi();
    const fetcher = async (url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(url), body: init?.body ? String(init.body) : undefined });
      const path = String(url).replace(config.serviceUrl, "");
      const face_check = { passed: false, override: false, stage: "frontal", similarity: 0.12 };
      if (path === "/v1/live/quizzes/3/sessions") return new Response(JSON.stringify({ sessions: [{ ...held, face_check }] }));
      return new Response(JSON.stringify({ id: 1 }));
    };
    const api = new ReviewApi(config.serviceUrl, config.token, fetcher as typeof fetch);
    render(<App config={{ ...config, caps: ["invigilate"] }} api={api} />);
    await screen.findByText("Held at face check (match 0.12)");
    expect(screen.queryByRole("button", { name: "Warn" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Let in without face check" }));
    fireEvent.change(screen.getByLabelText("Let in without face check: reason"), { target: { value: "Showed student ID on camera" } });
    fireEvent.click(screen.getByRole("button", { name: "Send let in without face check" }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/actions"))).toBe(true));
    expect(JSON.parse(calls.find((c) => c.url.endsWith("/actions"))!.body!).type).toBe("face_override");
  });
});
