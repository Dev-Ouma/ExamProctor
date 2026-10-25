/**
 * Live wall for invigilators: students currently sitting the quiz, newest camera image, risk band
 * and recent flags. Actions need a reason; the student sees every action.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, type DashboardConfig, type LiveAction, type LiveSession, type ReviewApi } from "./api";
import { BAND_LABELS, FLAG_LABELS, clock, label } from "./labels";

const POLL_MS = 15_000;
const THROTTLE_MS = 2_000;

export const ACTION_LABELS: Record<LiveAction, string> = {
  warn: "Warn",
  message: "Message",
  pause: "Pause",
  resume: "Resume",
  terminate: "End session",
};

export function LiveWall({ api, config, onOpen }: { api: ReviewApi; config: DashboardConfig; onOpen: (id: string) => void }) {
  const [sessions, setSessions] = useState<LiveSession[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [updated, setUpdated] = useState<string | null>(null);
  const pending = useRef<number | undefined>(undefined);

  const load = useCallback(() => {
    api
      .live(config.quizId)
      .then((body) => {
        setSessions(body.sessions);
        setUpdated(body.server_time);
        setError(null);
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "The live service could not be reached."));
  }, [api, config.quizId]);

  // Refresh on a timer, and sooner when the stream says something changed.
  useEffect(() => {
    load();
    const poll = window.setInterval(load, POLL_MS);
    let ws: WebSocket | undefined;
    let retry: number | undefined;
    let stopped = false;
    const connect = (delay: number) => {
      if (typeof WebSocket === "undefined") return;
      ws = api.stream(
        config.quizId,
        (type) => {
          setConnected(true);
          if (type === "ping" || type === "hello" || pending.current) return;
          pending.current = window.setTimeout(() => {
            pending.current = undefined;
            load();
          }, THROTTLE_MS);
        },
        (code) => {
          setConnected(false);
          if (!stopped && code !== 4401 && code !== 4403) {
            retry = window.setTimeout(() => connect(Math.min(delay * 2, 30_000)), delay);
          }
        },
      );
    };
    connect(1000);
    return () => {
      stopped = true;
      window.clearInterval(poll);
      window.clearTimeout(retry);
      window.clearTimeout(pending.current);
      ws?.close();
    };
  }, [api, config.quizId, load]);

  if (error && !sessions) return <div className="alert alert-danger">{error}</div>;
  if (!sessions) return <p>Loading the live wall…</p>;

  const online = sessions.filter((s) => s.online && !s.ended_at).length;
  return (
    <section aria-label="Live wall">
      <p className="ep-muted ep-small">
        {online} online · {sessions.length} shown (ended sessions stay for 10 minutes) ·{" "}
        {connected ? "live updates on" : "refreshing every 15 s"}
        {updated ? ` · updated ${clock(updated)}` : ""}
      </p>
      {error && <div className="alert alert-warning">{error}</div>}
      {sessions.length === 0 ? (
        <p className="ep-muted">Nobody is sitting this quiz right now.</p>
      ) : (
        <div className="ep-wall">
          {sessions.map((s) => (
            <LiveCard key={s.session_id} s={s} api={api} config={config} onOpen={onOpen} onDone={load} />
          ))}
        </div>
      )}
    </section>
  );
}

function stateOf(s: LiveSession): { text: string; cls: string } {
  if (s.terminated) return { text: "Ended by invigilator", cls: "ep-state-ended" };
  if (s.ended_at) return { text: "Finished", cls: "ep-state-ended" };
  if (s.paused) return { text: "Paused", cls: "ep-state-paused" };
  if (s.online) return { text: "Online", cls: "ep-state-online" };
  return { text: s.last_seen_at ? `Not seen since ${clock(s.last_seen_at)}` : "Not seen yet", cls: "ep-state-stale" };
}

export function LiveCard({
  s,
  api,
  config,
  onOpen,
  onDone,
}: {
  s: LiveSession;
  api: ReviewApi;
  config: DashboardConfig;
  onOpen: (id: string) => void;
  onDone: () => void;
}) {
  const person = config.people[String(s.moodle_user_id)];
  const state = stateOf(s);
  const [action, setAction] = useState<LiveAction | null>(null);
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const active = !s.ended_at;
  const available: LiveAction[] = active ? ["warn", "message", s.paused ? "resume" : "pause", "terminate"] : [];
  const ready = action && reason.trim().length >= 3 && (action !== "message" || message.trim()) && (action !== "terminate" || confirm);

  const send = async () => {
    if (!action || !ready) return;
    setBusy(true);
    setNote(null);
    try {
      await api.act(s.session_id, action, reason.trim(), message.trim());
      setNote(`${ACTION_LABELS[action]} sent.`);
      setAction(null);
      setReason("");
      setMessage("");
      setConfirm(false);
      onDone();
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : "Could not send.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className={`ep-livecard ep-band-border-${s.band ?? "pending"}`} aria-label={person?.name ?? `User ${s.moodle_user_id}`}>
      <header className="ep-livehead">
        <button type="button" className="btn btn-link p-0 ep-livename" onClick={() => onOpen(s.session_id)}>
          {person?.name ?? `User #${s.moodle_user_id}`}
        </button>
        <span className={`ep-state ${state.cls}`}>{state.text}</span>
      </header>
      <div className="ep-thumb">
        {s.latest_camera ? (
          <img src={s.latest_camera.url} alt={`Latest camera image of ${person?.name ?? "student"} at ${clock(s.latest_camera.captured_at)}`} />
        ) : (
          <div className="ep-gone">No camera image yet</div>
        )}
        {s.latest_camera && (
          <span className="ep-thumbinfo">
            {clock(s.latest_camera.captured_at)} · {s.latest_camera.faces} face{s.latest_camera.faces === 1 ? "" : "s"}
          </span>
        )}
      </div>
      <div className="ep-livefacts">
        <span className={`ep-band ep-band-${s.band ?? "pending"}`}>{BAND_LABELS[s.band ?? "pending"]}</span>{" "}
        {s.integrity_score === null ? "" : Math.round(s.integrity_score)} · {s.flag_count} flag{s.flag_count === 1 ? "" : "s"}
        {s.client_health && Number(s.client_health.queued_uploads) > 0 && (
          <span className="ep-muted"> · {String(s.client_health.queued_uploads)} images waiting to upload</span>
        )}
      </div>
      {s.recent_flags.length > 0 && (
        <ul className="ep-recent">
          {s.recent_flags.map((f, i) => (
            <li key={i}>
              {clock(f.start)} {label(FLAG_LABELS, f.type)}
            </li>
          ))}
        </ul>
      )}
      {s.actions.length > 0 && (
        <p className="ep-small ep-muted">
          Last action: {ACTION_LABELS[s.actions.at(-1)!.type as LiveAction] ?? s.actions.at(-1)!.type} by{" "}
          {s.actions.at(-1)!.actor_name || "invigilator"} at {clock(s.actions.at(-1)!.created_at)}
          {s.actions.at(-1)!.acked_at ? " · seen by student" : ""}
        </p>
      )}
      {available.length > 0 && (
        <div className="ep-actions">
          {available.map((a) => (
            <button
              key={a}
              type="button"
              className={`btn btn-sm ${a === "terminate" ? "btn-outline-danger" : "btn-outline-secondary"} ${action === a ? "active" : ""}`}
              onClick={() => setAction(action === a ? null : a)}
              aria-pressed={action === a}
            >
              {ACTION_LABELS[a]}
            </button>
          ))}
        </div>
      )}
      {action && (
        <form
          className="ep-actionform"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <input
            className="form-control form-control-sm"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason (required, kept in the audit log)"
            aria-label={`${ACTION_LABELS[action]}: reason`}
            maxLength={1000}
          />
          {(action === "warn" || action === "message") && (
            <textarea
              className="form-control form-control-sm"
              rows={2}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={action === "message" ? "Message the student sees (required)" : "What the student sees (optional; the reason is shown otherwise)"}
              aria-label={`${ACTION_LABELS[action]}: message to student`}
              maxLength={1000}
            />
          )}
          {action === "terminate" && (
            <label className="ep-small">
              <input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} /> End this session and submit
              the attempt now. A reviewer still decides any outcome.
            </label>
          )}
          <button type="submit" className={`btn btn-sm ${action === "terminate" ? "btn-danger" : "btn-primary"}`} disabled={!ready || busy}>
            Send {ACTION_LABELS[action].toLowerCase()}
          </button>
        </form>
      )}
      {note && (
        <p role="status" className="ep-small">
          {note}
        </p>
      )}
    </article>
  );
}
