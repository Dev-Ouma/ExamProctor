"""Headless candidate simulator and load test (M7, spec section 10).

Each simulated candidate does what the browser SDK does, against the real API: launch-token
exchange, consent, pre-check, then camera (and for 60 % of them screen) snapshots through presigned
PUTs, event batches and heartbeats. A share of candidates misbehave on a script (camera covered,
second window, copy-paste) so the AI pipeline and the live wall see realistic flags.

The simulator signs launch tokens itself with the Moodle shared secret, so it needs no Moodle; run
`sink` as the webhook target instead of Moodle. Never point a full ramp at a shared server.

    python -m examproctor_service.simulate sink --port 9000
    python -m examproctor_service.simulate run --base http://localhost:8000 --users 5000 \\
        --ramp-s 300 --duration-s 900 --secret "$EXAMPROCTOR_SHARED_SECRET" --report load.md
"""

import argparse
import asyncio
import hashlib
import json
import multiprocessing
import os
import random
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import jwt

SPEC_TARGETS = {"p95_ms": 300, "upload_success": 0.99, "flag_to_wall_p95_s": 15}


@dataclass
class Stats:
    latency: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    errors: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    statuses: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    uploads_ok: int = 0
    uploads_failed: int = 0
    started: int = 0
    ready: int = 0
    active: int = 0
    flag_latency: list[float] = field(default_factory=list)

    def plain(self) -> dict[str, Any]:
        """Picklable copy for returning from a worker process."""
        return {
            "latency": dict(self.latency),
            "errors": dict(self.errors),
            "statuses": dict(self.statuses),
            "uploads_ok": self.uploads_ok,
            "uploads_failed": self.uploads_failed,
            "started": self.started,
            "ready": self.ready,
            "flag_latency": self.flag_latency,
        }

    def merge(self, other: dict[str, Any]) -> None:
        for name, values in other["latency"].items():
            self.latency[name].extend(values)
        for key in ("errors", "statuses"):
            for name, n in other[key].items():
                getattr(self, key)[name] += n
        for key in ("uploads_ok", "uploads_failed", "started", "ready"):
            setattr(self, key, getattr(self, key) + other[key])
        self.flag_latency.extend(other["flag_latency"])

    def record(self, name: str, seconds: float, status: int) -> None:
        self.latency[name].append(seconds * 1000)
        if status >= 400 or status == 0:
            self.errors[name] += 1
            self.statuses[f"{name} {status}"] += 1


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))]


def jpeg(size: int, seed: int, dark: bool = False) -> bytes:
    """A synthetic JPEG of about `size` bytes: noise compresses badly, so size is easy to hit."""
    import cv2
    import numpy as np

    rng = np.random.default_rng(seed)
    side = 320
    while True:
        image = rng.integers(0, 40 if dark else 255, (side * 3 // 4, side, 3), dtype=np.uint8)
        data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 60])[1].tobytes()
        if len(data) >= size * 0.8 or side > 1280:
            return data
        side += 40


class Candidate:
    def __init__(self, n: int, args: argparse.Namespace, client: httpx.AsyncClient, stats: Stats, images: dict) -> None:
        self.n = n
        self.args = args
        self.client = client
        self.stats = stats
        self.images = images
        self.desktop = random.random() < args.desktop_share
        self.misbehaves = random.random() < args.misbehave_share
        self.headers: dict[str, str] = {}
        self.sid = ""
        self.seq = defaultdict(int)

    async def call(self, name: str, method: str, path: str, **kwargs: Any) -> httpx.Response | None:
        start = time.perf_counter()
        try:
            response = await self.client.request(method, self.args.base + path, headers=self.headers, **kwargs)
        except httpx.HTTPError:
            self.stats.record(name, time.perf_counter() - start, 0)
            return None
        self.stats.record(name, time.perf_counter() - start, response.status_code)
        return response

    def launch_token(self) -> str:
        now = int(time.time())
        claims = {
            "iss": self.args.issuer,
            "aud": "examproctor-service",
            "sub": str(self.args.user_base + self.n),
            "course_id": self.args.course_id,
            "cmid": self.args.cmid,
            "quiz_id": self.args.quiz_id,
            "attempt_id": None,
            "policy": {"camera": True, "screen": self.desktop, "identity": False, "strict": False},
            "iat": now,
            "exp": now + 120,
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(claims, self.args.secret, algorithm="HS256")

    async def start(self) -> bool:
        r = await self.call("exchange", "POST", "/v1/sessions/exchange", json={"launch_token": self.launch_token()})
        if r is None or r.status_code != 200:
            return False
        body = r.json()
        self.sid = body["session_id"]
        self.headers = {"Authorization": f"Bearer {body['session_token']}"}
        consent = {"text_version": body["consent_text_version"], "accepted": True}
        r = await self.call("consent", "POST", f"/v1/sessions/{self.sid}/consent", json=consent)
        if r is None or r.status_code != 200:
            return False
        precheck = {
            "camera": "ok",
            "screen": "ok" if self.desktop else "unsupported",
            "screen_surface": "monitor" if self.desktop else None,
            "network_ok": True,
        }
        r = await self.call("precheck", "POST", f"/v1/sessions/{self.sid}/precheck", json=precheck)
        return r is not None and r.status_code == 200 and r.json().get("status") == "ready"

    async def upload(self, kind: str, data: bytes) -> None:
        seq = self.seq[kind]
        self.seq[kind] += 1
        body = {
            "kind": kind,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "seq": seq,
            "captured_at": datetime.now(UTC).isoformat(),
        }
        for _attempt in range(3):  # the SDK retries from its queue; three tries is the budget here
            r = await self.call("presign", "POST", f"/v1/sessions/{self.sid}/uploads/presign", json=body)
            if r is None or r.status_code != 200:
                await asyncio.sleep(2)
                continue
            presigned = r.json()
            if not presigned.get("already_uploaded"):
                start = time.perf_counter()
                try:
                    put = await self.client.put(presigned["url"], content=data, headers=presigned["headers"])
                    self.stats.record("put", time.perf_counter() - start, put.status_code)
                    if put.status_code >= 300:
                        await asyncio.sleep(2)
                        continue
                except httpx.HTTPError:
                    self.stats.record("put", time.perf_counter() - start, 0)
                    await asyncio.sleep(2)
                    continue
                r = await self.call(
                    "complete", "POST", f"/v1/sessions/{self.sid}/uploads/complete", json={"key": presigned["key"]}
                )
                if r is None or r.status_code != 200:
                    await asyncio.sleep(2)
                    continue
            self.stats.uploads_ok += 1
            return
        self.stats.uploads_failed += 1

    def events(self, t: float) -> list[dict[str, Any]]:
        now = datetime.now(UTC).isoformat()
        out = [{"type": "question_shown", "ts": now, "data": {"question": f"question-{self.n}-{int(t) % 10 + 1}"}}]
        if self.misbehaves and random.random() < 0.15:
            q = f"question-{self.n}-{int(t) % 10 + 1}"
            out += [
                {"type": "copy", "ts": now, "data": {"question": q}},
                {"type": "blur", "ts": now, "data": {}},
                {"type": "focus", "ts": now, "data": {}},
                {"type": "paste", "ts": now, "data": {"question": q}},
            ]
        return out

    async def run(self, until: float) -> None:
        self.stats.started += 1
        if not await self.start():
            return
        self.stats.ready += 1
        self.stats.active += 1
        speed = self.args.speed
        camera_every, screen_every = 30 / speed, 30 / speed
        beat_every, events_every = 10 / speed, 5 / speed
        t0 = time.monotonic()
        # Spread candidates across the interval so uploads do not arrive in lock-step.
        next_camera = t0 + random.uniform(0, camera_every)
        next_screen = t0 + random.uniform(0, screen_every)
        next_beat = t0 + random.uniform(0, beat_every)
        next_events = t0 + random.uniform(0, events_every)
        try:
            while time.monotonic() < until:
                now = time.monotonic()
                if now >= next_camera:
                    covered = self.misbehaves and random.random() < 0.3
                    await self.upload("camera", self.images["dark" if covered else "camera"])
                    next_camera += camera_every
                if self.desktop and now >= next_screen:
                    await self.upload("screen", self.images["screen"])
                    next_screen += screen_every
                if now >= next_beat:
                    await self.call(
                        "heartbeat", "POST", f"/v1/sessions/{self.sid}/heartbeat", json={"queued_uploads": 0}
                    )
                    next_beat += beat_every
                if now >= next_events:
                    await self.call(
                        "events", "POST", f"/v1/sessions/{self.sid}/events", json={"events": self.events(now - t0)}
                    )
                    next_events += events_every
                await asyncio.sleep(max(0.05, min(next_camera, next_beat, next_events) - time.monotonic()))
            await self.call("finish", "POST", f"/v1/sessions/{self.sid}/finish")
        finally:
            self.stats.active -= 1


async def watch_flags(args: argparse.Namespace, stats: Stats, until: float) -> None:
    """Capture -> flag visible on the live wall: covered-camera frames should show as NO_FACE or
    CAMERA_OBSTRUCTED. Rules need sustained evidence, so the clock starts at the capture of the
    frame that completed the flag (its end) and stops when the live endpoint first lists it.
    Flags from earlier runs on the same quiz are ignored."""
    run_started = datetime.now(UTC)
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": args.issuer,
            "aud": "examproctor-staff",
            "sub": "1",
            "name": "Load test",
            "course_id": args.course_id,
            "quiz_id": args.quiz_id,
            "caps": ["review", "invigilate"],
            "iat": now,
            "exp": now + 7000,
        },
        args.secret,
        algorithm="HS256",
    )
    seen: set[tuple[str, str]] = set()
    async with httpx.AsyncClient(timeout=60) as client:
        while time.monotonic() < until:
            await asyncio.sleep(2)
            start = time.perf_counter()
            try:
                r = await client.get(
                    f"{args.base}/v1/live/quizzes/{args.quiz_id}/sessions", headers={"Authorization": f"Bearer {token}"}
                )
            except httpx.HTTPError:
                stats.record("live_wall", time.perf_counter() - start, 0)
                continue
            stats.record("live_wall", time.perf_counter() - start, r.status_code)
            if r.status_code != 200:
                continue
            seen_at = datetime.now(UTC)
            for s in r.json()["sessions"]:
                for f in s["recent_flags"]:
                    k = (s["session_id"], f["start"])
                    if k not in seen and f["type"] in ("NO_FACE", "CAMERA_OBSTRUCTED", "BLANK_CAPTURE"):
                        seen.add(k)
                        done = datetime.fromisoformat(f.get("end") or f["start"])
                        if done >= run_started:
                            stats.flag_latency.append((seen_at - done).total_seconds())


async def progress(stats: Stats, until: float) -> None:
    while time.monotonic() < until:
        await asyncio.sleep(15)
        hb = stats.latency.get("heartbeat", [])[-2000:]
        print(
            f"active={stats.active} ready={stats.ready}/{stats.started} uploads ok={stats.uploads_ok} "
            f"failed={stats.uploads_failed} heartbeat p95={pct(hb, 95):.0f}ms errors={sum(stats.errors.values())}",
            flush=True,
        )


async def run(args: argparse.Namespace, first: int = 0, count: int | None = None, watch: bool = True) -> Stats:
    """Simulate candidates first..first+count, spreading their starts over the ramp."""
    count = args.users if count is None else count
    stats = Stats()
    images = {
        "camera": jpeg(args.image_kb * 1000, 1),
        "dark": jpeg(args.image_kb * 1000 // 3, 2, dark=True),
        "screen": jpeg(args.image_kb * 1000, 3),
    }
    if args.face_jpeg:
        images["camera"] = Path(args.face_jpeg).read_bytes()
    limits = httpx.Limits(max_connections=args.connections, max_keepalive_connections=args.connections)
    started = time.monotonic()
    until = started + args.ramp_s + args.duration_s
    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        tasks = [asyncio.create_task(progress(stats, until))]
        if watch:
            tasks.append(asyncio.create_task(watch_flags(args, stats, until)))
        for n in range(first, first + count):
            c = Candidate(n, args, client, stats, images)
            tasks.append(asyncio.create_task(c.run(until)))
            await asyncio.sleep(args.ramp_s / max(1, count))
        await asyncio.gather(*tasks, return_exceptions=True)
    stats.elapsed = time.monotonic() - started  # type: ignore[attr-defined]
    return stats


def run_slice(args: argparse.Namespace, first: int, count: int, watch: bool) -> dict[str, Any]:
    random.seed(7 + first)
    stats = asyncio.run(run(args, first, count, watch))
    return stats.plain() | {"elapsed": getattr(stats, "elapsed", 0.0)}


def run_parallel(args: argparse.Namespace) -> Stats:
    """One event loop saturates near a thousand candidates, and a busy client loop inflates the
    latencies it measures. Split candidates across processes so the client is never the limit."""
    procs = max(1, min(args.procs, args.users))
    size = -(-args.users // procs)
    slices = [(args, i * size, min(size, args.users - i * size), i == 0) for i in range(procs) if i * size < args.users]
    with multiprocessing.get_context("spawn").Pool(len(slices)) as pool:
        parts = pool.starmap(run_slice, slices)
    stats = Stats()
    for part in parts:
        stats.merge(part)
    stats.elapsed = max(p["elapsed"] for p in parts)  # type: ignore[attr-defined]
    return stats


def report(args: argparse.Namespace, stats: Stats) -> str:
    api = [n for n in stats.latency if n not in ("put", "live_wall")]
    all_api = [v for n in api for v in stats.latency[n]]
    total = stats.uploads_ok + stats.uploads_failed
    upload_rate = stats.uploads_ok / total if total else 0.0
    flag_p95 = pct(stats.flag_latency, 95)
    rows = [
        f"| {n} | {len(v)} | {pct(v, 50):.0f} | {pct(v, 95):.0f} | {pct(v, 99):.0f} | {stats.errors.get(n, 0)} |"
        for n, v in sorted(stats.latency.items())
    ]
    verdict = lambda ok: "pass" if ok else "**miss**"  # noqa: E731
    p95 = pct(all_api, 95)
    lines = [
        f"# Load test {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Target {args.base}; {args.users} candidates, ramp {args.ramp_s} s, steady {args.duration_s} s, "
        f"time speed x{args.speed} (intervals divided by it), {args.desktop_share:.0%} desktop, "
        f"{args.misbehave_share:.0%} scripted misbehaviour, ~{args.image_kb} KB images, {args.procs} client processes.",
        "",
        f"Candidates ready: {stats.ready} of {stats.started}. Elapsed {getattr(stats, 'elapsed', 0):.0f} s.",
        "",
        "| Target (spec 10) | Result | Verdict |",
        "| --- | --- | --- |",
        f"| API p95 < {SPEC_TARGETS['p95_ms']} ms | {p95:.0f} ms | {verdict(p95 < SPEC_TARGETS['p95_ms'])} |",
        f"| Upload success >= 99 % | {upload_rate:.2%} ({stats.uploads_ok}/{total}) | "
        f"{verdict(upload_rate >= SPEC_TARGETS['upload_success'])} |",
        f"| Capture -> flag on live wall p95 < 15 s | {flag_p95:.1f} s (n={len(stats.flag_latency)}) | "
        f"{verdict(bool(stats.flag_latency) and flag_p95 < SPEC_TARGETS['flag_to_wall_p95_s'])} |",
        "",
        "| Call | Count | p50 ms | p95 ms | p99 ms | Errors |",
        "| --- | --- | --- | --- | --- | --- |",
        *rows,
    ]
    if stats.statuses:
        lines += ["", "Error statuses: " + ", ".join(f"{k}: {v}" for k, v in sorted(stats.statuses.items()))]
    return "\n".join(lines) + "\n"


def sink(port: int) -> None:
    """Stand-in for Moodle's webhook endpoint during load tests: accepts everything."""
    import uvicorn
    from fastapi import FastAPI

    app = FastAPI()
    counts: dict[str, int] = defaultdict(int)

    @app.post("/{path:path}")
    async def accept(body: dict[str, Any]) -> dict[str, Any]:
        counts[body.get("event", "?")] += 1
        return {"ok": True}

    @app.get("/")
    async def summary() -> dict[str, int]:
        return dict(counts)

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")  # noqa: S104 - test sink in a container


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("sink")
    s.add_argument("--port", type=int, default=9000)
    r = sub.add_parser("run")
    r.add_argument("--base", required=True, help="service base URL, e.g. http://localhost:8000")
    r.add_argument(
        "--secret",
        default=os.environ.get("EXAMPROCTOR_SHARED_SECRET", ""),
        help="Moodle shared secret; defaults to $EXAMPROCTOR_SHARED_SECRET (keeps it out of the process list)",
    )
    r.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) // 2), help="client processes")
    r.add_argument("--issuer", default="http://localhost:8080")
    r.add_argument("--users", type=int, default=100)
    r.add_argument("--ramp-s", type=int, default=60)
    r.add_argument("--duration-s", type=int, default=300)
    r.add_argument("--speed", type=float, default=1.0, help="divide capture intervals by this")
    r.add_argument("--desktop-share", type=float, default=0.6)
    r.add_argument("--misbehave-share", type=float, default=0.1)
    r.add_argument("--image-kb", type=int, default=50)
    r.add_argument("--face-jpeg", help="optional real face photo (consented) for camera frames")
    r.add_argument("--connections", type=int, default=1000)
    r.add_argument("--quiz-id", type=int, default=990001)
    r.add_argument("--course-id", type=int, default=990001)
    r.add_argument("--cmid", type=int, default=990001)
    r.add_argument("--user-base", type=int, default=9_000_000)
    r.add_argument("--report", help="write a markdown report here")
    r.add_argument("--json", help="write raw percentiles as JSON here")
    args = parser.parse_args()
    if args.command == "sink":
        sink(args.port)
        return
    if not args.secret:
        parser.error("set EXAMPROCTOR_SHARED_SECRET or pass --secret")
    stats = run_parallel(args)
    text = report(args, stats)
    print(text)
    if args.report:
        Path(args.report).write_text(text)
    if args.json:
        Path(args.json).write_text(
            json.dumps({n: {"p50": pct(v, 50), "p95": pct(v, 95), "count": len(v)} for n, v in stats.latency.items()})
        )


if __name__ == "__main__":
    main()
