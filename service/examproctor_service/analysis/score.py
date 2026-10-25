"""Integrity score: a triage aid for reviewers, never a probability of cheating (spec 9)."""

from dataclasses import dataclass
from typing import Any

from .rules import Flag

VERSION = "v1"

# Points per unit of severity x confidence. Per-exam overrides arrive with the admin UI (M5).
WEIGHTS: dict[str, float] = {
    "IDENTITY_MISMATCH": 6,
    "MULTIPLE_FACES": 4,
    "COPY_PASTE_SEQUENCE": 4,
    "NO_FACE": 3,
    "CAMERA_OBSTRUCTED": 3,
    "MULTIPLE_SCREENS": 3,
    "FOCUS_LOSS": 2,
    "BLANK_CAPTURE": 2,
    "ATTENTION_AWAY": 1,
    "CONTEXT_MENU_ON_QUESTION": 1,
}
DURATIONAL = {
    "NO_FACE",
    "CAMERA_OBSTRUCTED",
    "FOCUS_LOSS",
    "ATTENTION_AWAY",
    "MULTIPLE_FACES",
    "BLANK_CAPTURE",
}
BANDS = ((80, "clear"), (50, "review"), (0, "high"))


@dataclass
class Score:
    value: float
    band: str
    reasons: list[dict[str, Any]]
    version: str = VERSION


def duration_factor(flag: Flag) -> float:
    return min(1 + flag.duration_s / 60, 3.0) if flag.type in DURATIONAL else 1.0


def compute(flags: list[Flag], weights: dict[str, float] = WEIGHTS) -> Score:
    reasons = []
    total = 0.0
    for i, f in enumerate(flags):
        points = weights.get(f.type, 0) * f.severity * f.confidence * duration_factor(f)
        if points <= 0:
            continue
        total += points
        reasons.append(
            {
                "flag_index": i,
                "type": f.type,
                "points": round(points, 2),
                "start": f.start.isoformat(),
                "question": f.question,
            }
        )
    value = max(0.0, min(100.0, 100.0 - total))
    band = next(name for floor, name in BANDS if value >= floor)
    reasons.sort(key=lambda r: -r["points"])
    return Score(round(value, 1), band, reasons)
