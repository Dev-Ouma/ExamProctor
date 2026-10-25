"""Data-subject requests from Moodle's Privacy API (Kenya DPA 2019): find, export and erase what
the service holds about one Moodle user. Signed by Moodle like the reference-photo calls.

Sessions under a legal hold are reported but never erased; Moodle shows that to the officer.
"""

import base64
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from .api import SettingsDep
from .objectstore import ObjectStore
from .refphotos import BodyDep
from .review import public_analysis
from .review_store import ReviewStore
from .store import Session

router = APIRouter(prefix="/v1/admin/privacy")
QuizFilter = Annotated[int | None, Query(ge=1)]


def deps(request: Request) -> tuple[ReviewStore, ObjectStore]:
    return request.app.state.reviews, request.app.state.objects


Deps = Annotated[tuple[ReviewStore, ObjectStore], Depends(deps)]


def prefix(env: str, session: Session) -> str:
    return f"{env}/{session.quiz_id}/{session.id}/"


@router.get("/users/{user_id}/quizzes")
async def user_quizzes(user_id: int, _: BodyDep, d: Deps) -> dict[str, Any]:
    return {"user_id": user_id, "quiz_ids": await d[0].user_quizzes(user_id)}


@router.get("/quizzes/{quiz_id}/users")
async def quiz_users(quiz_id: int, _: BodyDep, d: Deps) -> dict[str, Any]:
    return {"quiz_id": quiz_id, "user_ids": await d[0].quiz_users(quiz_id)}


@router.get("/users/{user_id}")
async def export_user(user_id: int, _: BodyDep, d: Deps, quiz_id: QuizFilter = None) -> dict[str, Any]:
    """Everything held about the user, images included, for the Moodle export bundle."""
    reviews, objects = d
    sessions = []
    for s in await reviews.user_sessions(user_id, quiz_id):
        uploads = []
        for u in await reviews.uploads(s.id):
            data = None if s.purged_at else await objects.get_bytes(u["key"])
            uploads.append(
                {
                    "kind": u["kind"],
                    "seq": u["seq"],
                    "captured_at": u["captured_at"],
                    "analysis": public_analysis(u["analysis"]),
                    "jpeg_base64": base64.b64encode(data).decode() if data else None,
                }
            )
        sessions.append(
            {
                "session_id": s.id,
                "quiz_id": s.quiz_id,
                "status": s.status,
                "consent_version": s.consent_version,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "legal_hold": s.legal_hold,
                "score": await reviews.score(s.id),
                "flags": await reviews.flags(s.id),
                "events": await reviews.events(s.id),
                "reviews": [r.to_json() for r in await reviews.reviews(s.id)],
                "uploads": uploads,
            }
        )
    await reviews.audit("moodle:privacy", "privacy_export", f"user:{user_id}", None, {"quiz_id": quiz_id})
    return {"user_id": user_id, "sessions": sessions}


@router.delete("/users/{user_id}")
async def erase_user(
    user_id: int, _: BodyDep, d: Deps, settings: SettingsDep, quiz_id: QuizFilter = None
) -> dict[str, Any]:
    reviews, objects = d
    erased, held = [], []
    for s in await reviews.user_sessions(user_id, quiz_id):
        if s.legal_hold:
            held.append(s.id)
            continue
        await objects.delete_prefix(prefix(settings.env, s))
        await reviews.erase_session(s.id)
        erased.append(s.id)
    await reviews.audit(
        "moodle:privacy",
        "privacy_erase",
        f"user:{user_id}",
        None,
        {"quiz_id": quiz_id, "erased": len(erased), "held": held},
    )
    return {"user_id": user_id, "erased": erased, "held": held}
