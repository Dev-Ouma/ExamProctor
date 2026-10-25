"""Pre-check rules: decide whether a session may unlock the quiz attempt."""

from typing import Any, Literal

from pydantic import BaseModel

DeviceStatus = Literal["ok", "denied", "missing", "unsupported", "not_requested"]


class PrecheckResults(BaseModel):
    camera: DeviceStatus = "not_requested"
    screen: DeviceStatus = "not_requested"
    screen_surface: str | None = None  # browser displaySurface: monitor | window | browser
    # Firefox hides displaySurface; the SDK then reports whether the capture has the display's shape.
    screen_matches_display: bool | None = None
    microphone: DeviceStatus = "not_requested"
    network_ok: bool = True


def evaluate(policy: dict[str, Any], results: PrecheckResults) -> list[str]:
    """Return blocking reasons. Empty list means the candidate may start.

    Strict mode: every required device must be ok.
    Lenient mode: a missing or unsupported device is allowed (recorded as context);
    a denied permission always blocks, because the candidate chose to refuse.
    """
    strict = bool(policy.get("strict"))
    reasons: list[str] = []
    for device in ("camera", "screen"):
        if not policy.get(device):
            continue
        status = getattr(results, device)
        if status == "ok":
            continue
        if status == "denied" or strict or status == "not_requested":
            reasons.append(f"{device}_{status}")
    if policy.get("screen") and results.screen == "ok" and not whole_display(results):
        reasons.append("screen_not_whole_display")
    if not results.network_ok:
        reasons.append("network_unavailable")
    return reasons


def whole_display(results: PrecheckResults) -> bool:
    if results.screen_surface is not None:
        return results.screen_surface == "monitor"
    return results.screen_matches_display is True
