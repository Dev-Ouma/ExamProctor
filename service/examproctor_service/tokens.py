"""Launch tokens (minted by Moodle) and session tokens (minted here)."""

import time
from typing import Any

import jwt

from .config import Settings

REQUIRED_LAUNCH_CLAIMS = ["iss", "aud", "sub", "iat", "exp", "jti", "course_id", "cmid", "quiz_id"]


class TokenError(Exception):
    """A token is missing, malformed, expired, replayed or signed with the wrong key."""


def decode_launch_token(token: str, settings: Settings) -> dict[str, Any]:
    if not settings.moodle_shared_secret:
        raise TokenError("service has no Moodle shared secret configured")
    try:
        claims = jwt.decode(
            token,
            settings.moodle_shared_secret,
            algorithms=["HS256"],
            audience=settings.launch_audience,
            issuer=settings.moodle_issuer,
            options={"require": REQUIRED_LAUNCH_CLAIMS},
            leeway=5,
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if claims["exp"] - claims["iat"] > settings.launch_max_lifetime_s:
        raise TokenError("launch token lifetime too long")
    if not isinstance(claims.get("policy"), dict):
        raise TokenError("launch token has no policy")
    return claims


def mint_session_token(session_id: str, user_id: int, settings: Settings) -> str:
    now = int(time.time())
    payload = {"sid": session_id, "sub": str(user_id), "iat": now}
    payload["exp"] = now + settings.session_token_ttl_s
    return jwt.encode(payload, settings.session_signing_key, algorithm="HS256")


def decode_session_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.session_signing_key,
            algorithms=["HS256"],
            options={"require": ["sid", "sub", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc


STAFF_CAPS = {"review", "decide", "exportevidence", "invigilate"}
REQUIRED_STAFF_CLAIMS = ["iss", "aud", "sub", "iat", "exp", "course_id", "quiz_id", "caps"]


def decode_staff_token(token: str, settings: Settings) -> dict[str, Any]:
    """Staff token minted by Moodle for one quiz after a capability check there."""
    if not settings.moodle_shared_secret:
        raise TokenError("service has no Moodle shared secret configured")
    try:
        claims = jwt.decode(
            token,
            settings.moodle_shared_secret,
            algorithms=["HS256"],
            audience=settings.staff_audience,
            issuer=settings.moodle_issuer,
            options={"require": REQUIRED_STAFF_CLAIMS},
            leeway=5,
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if claims["exp"] - claims["iat"] > settings.staff_token_max_lifetime_s:
        raise TokenError("staff token lifetime too long")
    if not isinstance(claims["caps"], list) or not set(claims["caps"]) <= STAFF_CAPS:
        raise TokenError("staff token has unknown capabilities")
    return claims
