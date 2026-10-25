/**
 * One session: incident report header, playback, flags with reasons, event log, reviewer decision
 * and appeal. "Print / save as PDF" prints this page with the print stylesheet.
 */

import { useCallback, useEffect, useState } from "react";
import { ApiError, type DashboardConfig, type ReviewApi, type SessionReview } from "./api";
import { Player, type Seek } from "./Player";
import {
  APPEAL_LABELS,
  BAND_LABELS,
  DECISION_LABELS,
  EVENT_LABELS,
  FLAG_LABELS,
  KEY_EVENTS,
  clock,
  duration,
  formatTime,
  label,
} from "./labels";

interface Props {
  api: ReviewApi;
  config: DashboardConfig;
  sessionId: string;
  onBack: () => void;
  onChanged: () => void;
}

export function SessionDetail({ api, config, sessionId, onBack, onChanged }: Props) {
  const [data, setData] = useState<SessionReview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [seek, setSeek] = useState<Seek | undefined>();
  const [allEvents, setAllEvents] = useState(false);

  const load = useCallback(() => {
    api
      .session(sessionId)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Could not load this session."));
  }, [api, sessionId]);
  useEffect(load, [load]);

  // Image links expire; reload a little before they do so playback keeps working.
  useEffect(() => {
    if (!data) return;
    const t = window.setTimeout(load, Math.max(30, data.url_ttl_s - 30) * 1000);
    return () => window.clearTimeout(t);
  }, [data, load]);

  if (error) return <div className="alert alert-danger">{error}</div>;
  if (!data) return <p>Loading session…</p>;

  const s = data.session;
  const person = config.people[String(s.moodle_user_id)];
  const attempt = config.attempts[s.session_id];
  const canDecide = config.caps.includes("decide");
  const jump = (iso: string) => setSeek({ ts: Date.parse(iso), nonce: Date.now() });
  const reviewed = data.reviews.filter((r) => r.kind === "decision").at(-1);
  const appeal = data.reviews.filter((r) => r.kind === "appeal").at(-1);
  const gaps = Object.entries(s.precheck ?? {}).filter(([, v]) => v !== "ok" && v !== true && v !== null);
  const events = allEvents ? data.events : data.events.filter((e) => KEY_EVENTS.has(e.type));

  return (
    <div className="ep-detail">
      <div className="ep-noprint ep-toolbar">
        <button type="button" className="btn btn-link" onClick={onBack}>
          ← All sessions
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => window.print()}>
          Print / save as PDF
        </button>
        {attempt && (
          <a className="btn btn-link" href={attempt.url} target="_blank" rel="noreferrer">
            Open the Moodle attempt
          </a>
        )}
      </div>

      <header className="ep-report-head">
        <h3>
          Incident report: {person?.name ?? `User #${s.moodle_user_id}`}
          {person?.idnumber ? <small className="ep-muted"> ({person.idnumber})</small> : null}
        </h3>
        <p className="ep-muted">
          {config.courseName} · {config.quizName}
        </p>
        <dl className="ep-facts">
          <div>
            <dt>Integrity score</dt>
            <dd>
              {data.score ? (
                <>
                  <span className={`ep-band ep-band-${data.score.band}`}>{BAND_LABELS[data.score.band]}</span>{" "}
                  {Math.round(data.score.value)} / 100
                </>
              ) : (
                "Not scored yet"
              )}
            </dd>
          </div>
          <div>
            <dt>Started</dt>
            <dd>{formatTime(s.started_at) || "Did not start"}</dd>
          </div>
          <div>
            <dt>Ended</dt>
            <dd>{formatTime(s.ended_at) || "Not closed"}</dd>
          </div>
          <div>
            <dt>Duration</dt>
            <dd>{duration(s.started_at, s.ended_at) || "-"}</dd>
          </div>
          <div>
            <dt>Images</dt>
            <dd>
              {data.uploads.filter((u) => u.kind === "camera").length} camera,{" "}
              {data.uploads.filter((u) => u.kind === "screen").length} screen
            </dd>
          </div>
          <div>
            <dt>Decision</dt>
            <dd>{reviewed ? label(DECISION_LABELS, reviewed.value) : "Not reviewed"}</dd>
          </div>
          {appeal && (
            <div>
              <dt>Appeal</dt>
              <dd>{label(APPEAL_LABELS, appeal.value)}</dd>
            </div>
          )}
        </dl>
        <p className="ep-note">
          The score helps decide what to look at first. It is not a probability of cheating. A person decides, after
          looking at the evidence.
        </p>
        {gaps.length > 0 && (
          <p className="ep-note">
            Device context at start:{" "}
            {gaps.map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v).replace(/_/g, " ")}`).join("; ")}. Take this
            into account before reading the flags.
          </p>
        )}
        {s.purged && <div className="alert alert-info">Images were deleted under the retention policy. Flags and decisions remain.</div>}
      </header>

      <section>
        <h4>Playback</h4>
        <Player uploads={data.uploads} flags={data.flags} events={data.events} seek={seek} />
      </section>

      <section>
        <h4>Flags ({data.flags.length})</h4>
        {data.flags.length === 0 ? (
          <p className="ep-muted">No flags were raised.</p>
        ) : (
          <table className="table table-sm ep-table">
            <thead>
              <tr>
                <th>When</th>
                <th>What was seen</th>
                <th>Length</th>
                <th>Confidence</th>
                <th>Score impact</th>
                <th>Question</th>
                <th className="ep-noprint" />
              </tr>
            </thead>
            <tbody>
              {data.flags.map((f, i) => {
                const reason = data.score?.reasons.find((r) => r.flag_index === (f.index ?? i));
                return (
                  <tr key={i} className={`ep-sevrow-${Math.min(4, f.severity)}`}>
                    <td>{clock(f.start)}</td>
                    <td>
                      {label(FLAG_LABELS, f.type)}
                      {Object.keys(f.context).length > 0 && (
                        <div className="ep-muted ep-small">
                          Context:{" "}
                          {describeContext(f.context)}
                        </div>
                      )}
                    </td>
                    <td>{duration(f.start, f.end) || "moment"}</td>
                    <td>{Math.round(f.confidence * 100)}%</td>
                    <td>{reason ? `-${reason.points}` : "0"}</td>
                    <td>{f.question ?? ""}</td>
                    <td className="ep-noprint">
                      <button type="button" className="btn btn-link btn-sm" onClick={() => jump(f.start)}>
                        Show
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h4>
          Activity log{" "}
          <label className="ep-small ep-noprint">
            <input type="checkbox" checked={allEvents} onChange={(e) => setAllEvents(e.target.checked)} /> show all events
          </label>
        </h4>
        {events.length === 0 ? (
          <p className="ep-muted">No events recorded.</p>
        ) : (
          <ol className="ep-events">
            {events.map((e, i) => (
              <li key={i}>
                <button type="button" className="btn btn-link btn-sm ep-noprint" onClick={() => jump(e.ts)}>
                  {clock(e.ts)}
                </button>
                <span className="ep-printonly">{clock(e.ts)} </span>
                {label(EVENT_LABELS, e.type)}
                {e.data && "question" in e.data ? <span className="ep-muted"> (question {String(e.data.question)})</span> : null}
              </li>
            ))}
          </ol>
        )}
      </section>

      <section>
        <h4>Review history</h4>
        {data.reviews.length === 0 ? (
          <p className="ep-muted">No decisions yet.</p>
        ) : (
          <ul className="ep-history">
            {data.reviews.map((r, i) => (
              <li key={i}>
                <strong>{r.kind === "decision" ? label(DECISION_LABELS, r.value) : label(APPEAL_LABELS, r.value)}</strong> by{" "}
                {r.reviewer_name || `#${r.reviewer_id}`}, {formatTime(r.created_at)}
                {r.notes && <div className="ep-notes">{r.notes}</div>}
              </li>
            ))}
          </ul>
        )}
        {canDecide && (
          <div className="ep-noprint ep-forms">
            <DecisionForm
              title="Record a decision"
              options={DECISION_LABELS}
              notesRequired={(v) => v !== "no_issue"}
              submit={(v, n) => api.decide(s.session_id, v, n)}
              onDone={() => {
                load();
                onChanged();
              }}
            />
            <DecisionForm
              title="Record an appeal step"
              options={APPEAL_LABELS}
              notesRequired={() => true}
              submit={(v, n) => api.appeal(s.session_id, v, n)}
              onDone={() => {
                load();
                onChanged();
              }}
            />
          </div>
        )}
      </section>
      <p className="ep-printonly ep-small">
        Printed {formatTime(new Date().toISOString())}. Session {s.session_id}. Consent version {s.consent_version ?? "-"}.
        Score version {data.score?.version ?? "-"}.
      </p>
    </div>
  );
}

interface FormProps {
  title: string;
  options: Record<string, string>;
  notesRequired: (value: string) => boolean;
  submit: (value: string, notes: string) => Promise<unknown>;
  onDone: () => void;
}

export function DecisionForm({ title, options, notesRequired, submit, onDone }: FormProps) {
  const [value, setValue] = useState(Object.keys(options)[0]);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const needNotes = notesRequired(value) && !notes.trim();
  return (
    <form
      className="ep-form"
      onSubmit={async (e) => {
        e.preventDefault();
        if (needNotes) return;
        setBusy(true);
        setMessage(null);
        try {
          await submit(value, notes);
          setNotes("");
          setMessage("Saved.");
          onDone();
        } catch (err) {
          setMessage(err instanceof ApiError ? err.message : "Could not save.");
        } finally {
          setBusy(false);
        }
      }}
    >
      <h5>{title}</h5>
      <select className="form-select" value={value} onChange={(e) => setValue(e.target.value)} aria-label={title}>
        {Object.entries(options).map(([k, v]) => (
          <option key={k} value={k}>
            {v}
          </option>
        ))}
      </select>
      <textarea
        className="form-control"
        rows={3}
        maxLength={4000}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder={notesRequired(value) ? "Reasons (required): what you saw and where" : "Notes (optional)"}
        aria-label={`${title}: notes`}
      />
      <button type="submit" className="btn btn-primary" disabled={busy || needNotes}>
        Save
      </button>
      {message && (
        <span role="status" className="ep-small">
          {" "}
          {message}
        </span>
      )}
    </form>
  );
}

/** Flatten flag context ({device: {microphone: "not_requested"}}) into readable text. */
export function describeContext(context: Record<string, unknown>, prefix = ""): string {
  return Object.entries(context)
    .map(([k, v]) => {
      const key = `${prefix}${k.replace(/_/g, " ")}`;
      if (v && typeof v === "object") return describeContext(v as Record<string, unknown>, prefix);
      return `${key}: ${String(v).replace(/_/g, " ")}`;
    })
    .filter(Boolean)
    .join("; ");
}
