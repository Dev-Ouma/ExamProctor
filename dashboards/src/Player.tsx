/**
 * Session playback: steps through camera and screen snapshots in time order, like a slow video,
 * with flags and key events marked on the timeline. ExamProctor stores snapshots, not video.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import type { EventItem, FlagItem, UploadItem } from "./api";
import { EVENT_LABELS, FLAG_LABELS, KEY_EVENTS, clock, label } from "./labels";

export interface Seek {
  ts: number;
  nonce: number;
}

interface Props {
  uploads: UploadItem[];
  flags: FlagItem[];
  events: EventItem[];
  seek?: Seek;
}

const SPEEDS = [1, 2, 4, 8];
/** The analyser scales images so the longer side is at most this before detecting faces. */
const ANALYSED_MAX_SIDE = 640;

/** Last item at or before `ts`, else the first item. */
export function nearestBefore<T extends { t: number }>(items: T[], ts: number): T | undefined {
  let found: T | undefined;
  for (const item of items) {
    if (item.t <= ts) found = item;
    else break;
  }
  return found ?? items[0];
}

export function Player({ uploads, flags, events, seek }: Props) {
  const frames = useMemo(
    () =>
      uploads
        .filter((u) => u.kind === "camera" || u.kind === "screen")
        .map((u) => ({ ...u, t: Date.parse(u.captured_at) }))
        .sort((a, b) => a.t - b.t),
    [uploads],
  );
  const camera = useMemo(() => frames.filter((f) => f.kind === "camera"), [frames]);
  const screen = useMemo(() => frames.filter((f) => f.kind === "screen"), [frames]);
  // Step through whichever stream has more frames; show the other one at the same moment.
  const track = camera.length >= screen.length ? camera : screen;
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!playing) return;
    timer.current = window.setInterval(() => {
      setIndex((i) => {
        if (i + 1 >= track.length) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, 1000 / speed);
    return () => window.clearInterval(timer.current);
  }, [playing, speed, track.length]);

  useEffect(() => {
    if (!seek || !track.length) return;
    const target = nearestBefore(track, seek.ts);
    setIndex(Math.max(0, track.indexOf(target!)));
    setPlaying(false);
  }, [seek, track]);

  if (!track.length) {
    return <p className="ep-muted">No camera or screen images were stored for this session.</p>;
  }

  const current = track[Math.min(index, track.length - 1)];
  const cam = camera.length ? nearestBefore(camera, current.t) : undefined;
  const scr = screen.length ? nearestBefore(screen, current.t) : undefined;
  const t0 = track[0].t;
  const t1 = Math.max(track[track.length - 1].t, t0 + 1);
  const pos = (iso: string) => `${Math.min(100, Math.max(0, ((Date.parse(iso) - t0) / (t1 - t0)) * 100))}%`;
  const seekTo = (iso: string) => {
    const target = nearestBefore(track, Date.parse(iso));
    setIndex(Math.max(0, track.indexOf(target!)));
    setPlaying(false);
  };

  return (
    <section className="ep-player" aria-label="Session playback">
      <div className="ep-frames">
        {cam && <Frame title="Camera" frame={cam} />}
        {scr && <Frame title="Screen" frame={scr} />}
      </div>
      <div className="ep-controls">
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => setIndex(0)} aria-label="First image">
          ⏮
        </button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => setIndex((i) => Math.max(0, i - 1))} aria-label="Previous image">
          ◀
        </button>
        <button type="button" className="btn btn-primary btn-sm" onClick={() => setPlaying((p) => !p)}>
          {playing ? "Pause" : "Play"}
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => setIndex((i) => Math.min(track.length - 1, i + 1))}
          aria-label="Next image"
        >
          ▶
        </button>
        <label className="ep-speed">
          Speed{" "}
          <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
            {SPEEDS.map((s) => (
              <option key={s} value={s}>
                {s} images/s
              </option>
            ))}
          </select>
        </label>
        <span className="ep-muted">
          {clock(current.captured_at)} · image {index + 1} of {track.length}
        </span>
      </div>
      <input
        type="range"
        className="ep-scrubber"
        min={0}
        max={track.length - 1}
        value={index}
        onChange={(e) => {
          setIndex(Number(e.target.value));
          setPlaying(false);
        }}
        aria-label="Playback position"
      />
      <div className="ep-timeline" aria-label="Flags and events on the timeline">
        <div className="ep-cursor" style={{ left: pos(current.captured_at) }} />
        {flags.map((f, i) => (
          <button
            type="button"
            key={`f${i}`}
            className={`ep-mark ep-sev-${Math.min(4, f.severity)}`}
            style={{ left: pos(f.start) }}
            title={`${label(FLAG_LABELS, f.type)} at ${clock(f.start)}`}
            aria-label={`${label(FLAG_LABELS, f.type)} at ${clock(f.start)}`}
            onClick={() => seekTo(f.start)}
          />
        ))}
        {events
          .filter((e) => KEY_EVENTS.has(e.type))
          .map((e, i) => (
            <button
              type="button"
              key={`e${i}`}
              className="ep-event"
              style={{ left: pos(e.ts) }}
              title={`${label(EVENT_LABELS, e.type)} at ${clock(e.ts)}`}
              aria-label={`${label(EVENT_LABELS, e.type)} at ${clock(e.ts)}`}
              onClick={() => seekTo(e.ts)}
            />
          ))}
      </div>
      <p className="ep-muted ep-legend">
        <span className="ep-mark ep-sev-3 ep-inline" /> flag <span className="ep-event ep-inline" /> page event. Select a mark to jump there.
      </p>
    </section>
  );
}

function Frame({ title, frame }: { title: string; frame: UploadItem & { t: number } }) {
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const faces = frame.analysis?.faces ?? [];
  // Face boxes are in analysed-image pixels; convert to the displayed image's size.
  const scale = size ? Math.min(1, ANALYSED_MAX_SIDE / Math.max(size.w, size.h)) : 1;
  const aw = size ? size.w * scale : 1;
  const ah = size ? size.h * scale : 1;
  return (
    <figure className="ep-frame">
      <figcaption>
        {title} · {clock(frame.captured_at)}
        {frame.kind === "camera" && frame.analysis && (
          <span className="ep-muted"> · {faces.length} face{faces.length === 1 ? "" : "s"} detected</span>
        )}
      </figcaption>
      <div className="ep-imgwrap">
        {frame.url ? (
          <img
            src={frame.url}
            alt={`${title} snapshot at ${clock(frame.captured_at)}`}
            onLoad={(e) => setSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
          />
        ) : (
          <div className="ep-gone">Image deleted under the retention policy</div>
        )}
        {size &&
          frame.kind === "camera" &&
          faces.map((f, i) => (
            <span
              key={i}
              className="ep-facebox"
              style={{
                left: `${(f.box[0] / aw) * 100}%`,
                top: `${(f.box[1] / ah) * 100}%`,
                width: `${(f.box[2] / aw) * 100}%`,
                height: `${(f.box[3] / ah) * 100}%`,
              }}
            />
          ))}
      </div>
    </figure>
  );
}
