"""Flag rules (spec section 9). Pure functions over analysed frames and page events.

Rules prefer sustained evidence over single frames: one bad frame is noise, two in a row is a
pattern a reviewer should look at. Every flag keeps the evidence keys it came from and context
that may explain it (connectivity gaps, device limits), so reviewers can discount it.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .faces import SFACE_COSINE_THRESHOLD, cosine

YAW_AWAY = 0.35


@dataclass
class Frame:
    key: str
    kind: str  # camera | screen
    captured_at: datetime
    result: dict[str, Any]  # FrameResult.to_json() plus optional "embedding"


@dataclass
class PageEvent:
    type: str
    ts: datetime
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Flag:
    type: str
    severity: int  # 1 minor .. 4 serious
    confidence: float  # 0..1
    start: datetime
    end: datetime
    evidence: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    question: str | None = None

    @property
    def duration_s(self) -> float:
        return max(0.0, (self.end - self.start).total_seconds())

    def to_json(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "severity": self.severity,
            "confidence": round(self.confidence, 3),
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_s": round(self.duration_s, 1),
            "evidence": self.evidence,
            "context": self.context,
            "question": self.question,
        }


def runs(frames: list[Frame], predicate, min_len: int) -> list[list[Frame]]:
    """Consecutive frames matching `predicate`, kept when at least `min_len` long."""
    out: list[list[Frame]] = []
    current: list[Frame] = []
    for f in frames:
        if predicate(f):
            current.append(f)
        else:
            if len(current) >= min_len:
                out.append(current)
            current = []
    if len(current) >= min_len:
        out.append(current)
    return out


def _flag(type_: str, severity: int, confidence: float, group: list[Frame], **extra) -> Flag:
    return Flag(
        type_,
        severity,
        confidence,
        group[0].captured_at,
        group[-1].captured_at,
        [f.key for f in group],
        **extra,
    )


def camera_flags(frames: list[Frame], reference: list[float] | None) -> list[Flag]:
    cams = sorted((f for f in frames if f.kind == "camera"), key=lambda f: f.captured_at)
    faces = lambda f: len(f.result.get("faces", []))  # noqa: E731
    blank = lambda f: bool(f.result.get("blank"))  # noqa: E731
    flags = (
        [_flag("CAMERA_OBSTRUCTED", 2, 0.9, g) for g in runs(cams, blank, 2)]
        + [_flag("NO_FACE", 2, 0.8, g) for g in runs(cams, lambda f: not blank(f) and faces(f) == 0, 2)]
        + [_flag("MULTIPLE_FACES", 3, 0.8, g) for g in runs(cams, lambda f: faces(f) >= 2, 1)]
    )
    away = lambda f: faces(f) == 1 and abs(f.result["faces"][0]["yaw"]) > YAW_AWAY  # noqa: E731
    flags += [_flag("ATTENTION_AWAY", 1, 0.6, g) for g in runs(cams, away, 3)]
    if reference is not None:

        def mismatch(f: Frame) -> bool:
            emb = f.result.get("embedding")
            return emb is not None and faces(f) == 1 and cosine(emb, reference) < SFACE_COSINE_THRESHOLD

        for g in runs(cams, mismatch, 2):
            sims = [cosine(f.result["embedding"], reference) for f in g]
            margin = SFACE_COSINE_THRESHOLD - sum(sims) / len(sims)
            flags.append(
                _flag(
                    "IDENTITY_MISMATCH",
                    4,
                    min(1.0, 0.5 + margin * 2),
                    g,
                    context={"mean_similarity": round(sum(sims) / len(sims), 3)},
                )
            )
    return flags


def screen_flags(frames: list[Frame]) -> list[Flag]:
    screens = sorted((f for f in frames if f.kind == "screen"), key=lambda f: f.captured_at)
    return [_flag("BLANK_CAPTURE", 2, 0.7, g) for g in runs(screens, lambda f: bool(f.result.get("blank")), 2)]


AWAY_START = {"blur", "visibility_hidden"}
AWAY_END = {"focus", "visibility_visible"}


def event_flags(events: list[PageEvent]) -> list[Flag]:
    events = sorted(events, key=lambda e: e.ts)
    flags: list[Flag] = []
    left: datetime | None = None
    copied: dict[str, datetime] = {}  # question -> copy time
    left_after_copy: set[str] = set()
    for e in events:
        q = e.data.get("question")
        if e.type in AWAY_START and left is None:
            left = e.ts
            left_after_copy |= set(copied)
        elif e.type in AWAY_END and left is not None:
            seconds = (e.ts - left).total_seconds()
            if seconds >= 2:
                flags.append(Flag("FOCUS_LOSS", 2 if seconds > 10 else 1, 0.9, left, e.ts))
            left = None
        elif e.type == "copy" and q:
            copied[q] = e.ts
            left_after_copy.discard(q)
        elif e.type == "paste" and q and q in left_after_copy and e.ts - copied[q] <= timedelta(minutes=10):
            flags.append(Flag("COPY_PASTE_SEQUENCE", 3, 0.8, copied[q], e.ts, question=q))
            left_after_copy.discard(q)
        elif e.type == "contextmenu" and q:
            flags.append(Flag("CONTEXT_MENU_ON_QUESTION", 1, 0.9, e.ts, e.ts, question=q))
        elif e.type == "display_info" and e.data.get("extended"):
            flags.append(
                Flag(
                    "MULTIPLE_SCREENS",
                    2,
                    0.7,
                    e.ts,
                    e.ts,
                    context={"screens": e.data.get("screens")},
                )
            )
    return flags


def connectivity_windows(events: list[PageEvent]) -> list[tuple[datetime, datetime]]:
    windows, start = [], None
    for e in sorted(events, key=lambda e: e.ts):
        if e.type == "offline" and start is None:
            start = e.ts
        elif e.type == "online" and start is not None:
            windows.append((start, e.ts))
            start = None
    return windows


def add_context(flags: list[Flag], events: list[PageEvent], device: dict[str, Any]) -> list[Flag]:
    """Lower confidence of flags that overlap a connection drop; note device limits."""
    gaps = connectivity_windows(events)
    for f in flags:
        if any(s <= f.end and f.start <= e for s, e in gaps):
            f.context["connectivity_gap"] = True
            f.confidence *= 0.5
        if device:
            f.context.setdefault("device", device)
    return flags


def all_flags(
    frames: list[Frame],
    events: list[PageEvent],
    reference: list[float] | None,
    device: dict[str, Any] | None = None,
) -> list[Flag]:
    flags = camera_flags(frames, reference) + screen_flags(frames) + event_flags(events)
    return sorted(add_context(flags, events, device or {}), key=lambda f: f.start)
