"""Face gate for the pre-check: the student must show one clear, frontal face that matches the
institutional photo, then turn their head the way the service asks and look back (liveness).

The service drives every step from the frames it analyses itself, so the browser cannot claim a
pass. The challenge direction is random and expires, so a photo or a replayed video does not pass.
"""

import secrets
import time
from typing import Any

from .analysis.faces import SFACE_COSINE_THRESHOLD, FrameResult, cosine
from .refphotos import validate

# Consecutive good frontal frames needed before the head-turn challenge.
FRONTAL_FRAMES = 3
# |yaw| at or below this counts as looking at the camera; at or above TURNED counts as turned.
FRONTAL_YAW = 0.2
TURNED_YAW = 0.35
# The challenge must be finished within this many seconds, or it restarts with a new direction.
CHALLENGE_SECONDS = 30
# YuNet's yaw is nose minus eye midpoint in image x. The camera frame is not mirrored, so a head
# turned to the student's own left moves the nose to the image's right: positive yaw.
YAW_SIGN = {"left": 1.0, "right": -1.0}


def new_state(now: float | None = None) -> dict[str, Any]:
    return {
        "stage": "frontal",  # frontal -> turn -> return -> passed
        "good": 0,
        "challenge": secrets.choice(("left", "right")),
        "started": time.time() if now is None else now,
        "similarity": None,  # lowest match score seen on frontal frames
    }


def step(
    state: dict[str, Any] | None,
    frame: FrameResult,
    reference: list[float] | None,
    now: float | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Advance the gate by one frame. Returns the new state and the reason this frame failed."""
    now = time.time() if now is None else now
    if state is None or (state["stage"] != "passed" and now - state["started"] > CHALLENGE_SECONDS):
        state = new_state(now)
    if state["stage"] == "passed":
        return state, None
    state = dict(state)
    if state["stage"] == "turn":
        return turn_step(state, frame, now)
    reason = validate(frame)
    if reason is None and abs(frame.faces[0].yaw) > FRONTAL_YAW:
        reason = "look_at_camera"
    if reason is None and reference is not None:
        if frame.embedding is None:
            reason = "face_too_small"
        else:
            similarity = cosine(frame.embedding, reference)
            low = state["similarity"]
            state["similarity"] = round(similarity if low is None else min(low, similarity), 3)
            if similarity < SFACE_COSINE_THRESHOLD:
                reason = "not_same_person"
    if reason is not None:
        state["good"] = 0
        if state["stage"] == "return" and reason not in ("look_at_camera", "blurry"):
            # A different face or no face after the turn: start again so the turn cannot be faked
            # by swapping in a photo for the frontal frames.
            state = new_state(now) | {"similarity": state["similarity"]}
        return state, reason
    if state["stage"] == "return":
        state["stage"] = "passed"
        return state, None
    state["good"] += 1
    if state["good"] >= FRONTAL_FRAMES:
        state["stage"] = "turn"
    return state, None


def turn_step(state: dict[str, Any], frame: FrameResult, now: float) -> tuple[dict[str, Any], str | None]:
    if frame.decode_error:
        return state, "unreadable"
    if len(frame.faces) != 1:
        # Losing the face mid-turn restarts the challenge: a swap of faces must not pass.
        return new_state(now) | {"similarity": state["similarity"]}, "no_face" if not frame.faces else "multiple_faces"
    yaw = frame.faces[0].yaw * YAW_SIGN[state["challenge"]]
    if yaw >= TURNED_YAW:
        state["stage"] = "return"
        return state, None
    if yaw <= -TURNED_YAW:
        return state, "turn_other_way"
    return state, "turn_head"


def instruction(state: dict[str, Any]) -> str:
    """What the student should do next."""
    stage = state["stage"]
    if stage == "turn":
        return f"turn_{state['challenge']}"
    if stage == "return":
        return "look_back"
    if stage == "passed":
        return "done"
    return "hold_still"
