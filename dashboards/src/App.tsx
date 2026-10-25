/** Proctoring report for one quiz, mounted by local_examproctor/report.php. */

import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, type DashboardConfig, ReviewApi, type SessionRow, type Summary } from "./api";
import { APPEAL_LABELS, BAND_LABELS, DECISION_LABELS, FLAG_LABELS, formatTime, label } from "./labels";
import { SessionDetail } from "./SessionDetail";

export type Mode = "staging" | "live";

export function StagingBanner({ mode }: { mode: Mode }) {
  if (mode !== "staging") {
    return null;
  }
  return (
    <div role="status" className="ep-staging">
      Staging environment: synthetic data only
    </div>
  );
}

type Sort = "score" | "name" | "started" | "flags";

export function App({ config, api }: { config: DashboardConfig; api?: ReviewApi }) {
  const client = useMemo(() => api ?? new ReviewApi(config.serviceUrl, config.token), [api, config]);
  const [rows, setRows] = useState<SessionRow[] | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(() => new URLSearchParams(window.location.hash.slice(1)).get("session"));
  const [band, setBand] = useState("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("score");
  const [expired, setExpired] = useState(false);

  const name = useCallback(
    (r: SessionRow) => config.people[String(r.moodle_user_id)]?.name ?? `User #${r.moodle_user_id}`,
    [config.people],
  );

  const load = useCallback(() => {
    Promise.all([client.sessions(config.quizId), client.summary(config.quizId)])
      .then(([list, sum]) => {
        setRows(list);
        setSummary(sum);
      })
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 401) setExpired(true);
        setError(e instanceof ApiError ? `${e.message} (${e.code})` : "The proctoring service could not be reached.");
      });
  }, [client, config.quizId]);
  useEffect(load, [load]);

  useEffect(() => {
    const t = window.setTimeout(() => setExpired(true), config.tokenTtl * 1000);
    return () => window.clearTimeout(t);
  }, [config.tokenTtl]);

  useEffect(() => {
    window.location.hash = open ? `session=${open}` : "";
  }, [open]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = (rows ?? []).filter((r) => {
      if (band !== "all" && (r.band ?? "pending") !== band) return false;
      if (!q) return true;
      const p = config.people[String(r.moodle_user_id)];
      return `${p?.name ?? ""} ${p?.idnumber ?? ""} ${r.moodle_user_id}`.toLowerCase().includes(q);
    });
    const by: Record<Sort, (a: SessionRow, b: SessionRow) => number> = {
      score: (a, b) => (a.integrity_score ?? 101) - (b.integrity_score ?? 101),
      name: (a, b) => name(a).localeCompare(name(b)),
      started: (a, b) => (b.started_at ?? "").localeCompare(a.started_at ?? ""),
      flags: (a, b) => b.flag_count - a.flag_count,
    };
    return [...list].sort(by[sort]);
  }, [rows, band, query, sort, config.people, name]);

  const exportCsv = async () => {
    try {
      const csv = await client.exportCsv(config.quizId);
      // Add names here: the service never stores them.
      const lines = csv.trim().split(/\r?\n/);
      const withNames = lines.map((line, i) => {
        if (i === 0) return `name,idnumber,${line}`;
        const userId = line.split(",")[1];
        const p = config.people[userId];
        const cell = (v: string) => `"${v.replace(/"/g, '""')}"`;
        return `${cell(p?.name ?? "")},${cell(p?.idnumber ?? "")},${line}`;
      });
      const blob = new Blob([withNames.join("\r\n") + "\r\n"], { type: "text/csv" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `proctoring-${config.quizName.replace(/[^\w-]+/g, "_")}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Export failed.");
    }
  };

  return (
    <div className="ep-app">
      <StagingBanner mode={config.staging ? "staging" : "live"} />
      {expired && (
        <div className="alert alert-warning ep-noprint">
          This page's access has expired. <a href={window.location.href}>Reload</a> to continue.
        </div>
      )}
      {error && <div className="alert alert-danger">{error}</div>}
      {open ? (
        <SessionDetail api={client} config={config} sessionId={open} onBack={() => setOpen(null)} onChanged={load} />
      ) : rows === null ? (
        !error && <p>Loading sessions…</p>
      ) : (
        <>
          {summary && <SummaryCards summary={summary} />}
          <div className="ep-filters ep-noprint">
            <input
              className="form-control"
              type="search"
              placeholder="Search name or ID number"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search students"
            />
            <select className="form-select" value={band} onChange={(e) => setBand(e.target.value)} aria-label="Filter by band">
              <option value="all">All bands</option>
              {Object.entries(BAND_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            <select className="form-select" value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort by">
              <option value="score">Lowest score first</option>
              <option value="flags">Most flags first</option>
              <option value="started">Most recent first</option>
              <option value="name">Name</option>
            </select>
            {config.caps.includes("exportevidence") && (
              <button type="button" className="btn btn-secondary" onClick={exportCsv}>
                Download CSV
              </button>
            )}
            <button type="button" className="btn btn-secondary" onClick={() => window.print()}>
              Print / save as PDF
            </button>
          </div>
          {visible.length === 0 ? (
            <p className="ep-muted">No proctoring sessions match.</p>
          ) : (
            <table className="table table-hover ep-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Started</th>
                  <th>Status</th>
                  <th>Score</th>
                  <th>Flags</th>
                  <th>Images</th>
                  <th>Decision</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => (
                  <tr key={r.session_id} className="ep-row" onClick={() => setOpen(r.session_id)}>
                    <td>
                      <button type="button" className="btn btn-link p-0" onClick={() => setOpen(r.session_id)}>
                        {name(r)}
                      </button>
                      <div className="ep-muted ep-small">{config.people[String(r.moodle_user_id)]?.idnumber}</div>
                    </td>
                    <td>{formatTime(r.started_at) || <span className="ep-muted">not started</span>}</td>
                    <td>{statusText(r)}</td>
                    <td>
                      <span className={`ep-band ep-band-${r.band ?? "pending"}`}>{BAND_LABELS[r.band ?? "pending"]}</span>{" "}
                      {r.integrity_score === null ? "" : Math.round(r.integrity_score)}
                    </td>
                    <td>{r.flag_count}</td>
                    <td>
                      {r.uploads.camera ?? 0} cam / {r.uploads.screen ?? 0} scr
                    </td>
                    <td>
                      {label(DECISION_LABELS, r.decision) || <span className="ep-muted">to review</span>}
                      {r.appeal && <div className="ep-small">{label(APPEAL_LABELS, r.appeal)}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}

function statusText(r: SessionRow): string {
  if (r.purged) return "Images deleted";
  if (r.ended_at) return "Finished";
  if (r.status === "blocked") return "Blocked at pre-check";
  if (r.started_at) return "In progress or left";
  if (r.status === "ready") return "Passed pre-check";
  return "Pre-check not finished";
}

export function SummaryCards({ summary }: { summary: Summary }) {
  const maxFlag = Math.max(1, ...Object.values(summary.flag_types));
  return (
    <section className="ep-summary" aria-label="Quiz summary">
      <div className="ep-cards">
        <Card label="Sessions" value={summary.sessions} />
        <Card label="Finished" value={summary.finished} />
        <Card label="Blocked at pre-check" value={summary.blocked} />
        <Card label="Average score" value={summary.average_score === null ? "-" : Math.round(summary.average_score)} />
        {(["high", "review", "clear"] as const).map((b) => (
          <Card key={b} label={BAND_LABELS[b]} value={summary.bands[b] ?? 0} className={`ep-band-${b}`} />
        ))}
        <Card label="Still to review" value={summary.decisions.undecided ?? 0} />
      </div>
      {Object.keys(summary.flag_types).length > 0 && (
        <div className="ep-flagbars">
          <h4>Flags by type</h4>
          {Object.entries(summary.flag_types).map(([type, n]) => (
            <div key={type} className="ep-flagbar">
              <span className="ep-flagbar-label">{label(FLAG_LABELS, type)}</span>
              <span className="ep-flagbar-bar" style={{ width: `${(n / maxFlag) * 60}%` }} />
              <span className="ep-flagbar-n">{n}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function Card({ label: text, value, className = "" }: { label: string; value: string | number; className?: string }) {
  return (
    <div className={`ep-card ${className}`}>
      <div className="ep-card-value">{value}</div>
      <div className="ep-card-label">{text}</div>
    </div>
  );
}
