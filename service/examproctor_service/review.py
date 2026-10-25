"""Reviewer endpoints (spec 5.4 Review, M5): session list, evidence timeline, decisions, appeals,
quiz summary and CSV export.

Staff authenticate with a short-lived token Moodle mints for one quiz after its own capability
check. Every read of evidence and every write is recorded in the audit log. The score is a triage
aid; only a human decision is ever sent back to Moodle.
"""

import csv
import io
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from .api import SettingsDep, StoreDep, error
from .objectstore import ObjectStore
from .review_store import APPEALS, DECISIONS, Review, ReviewStore
from .store import Session
from .tokens import TokenError, decode_staff_token

router = APIRouter(prefix="/v1/review")
PAGE = 200


def get_reviews(request: Request) -> ReviewStore:
    return request.app.state.reviews


def get_objects(request: Request) -> ObjectStore:
    return request.app.state.objects


ReviewsDep = Annotated[ReviewStore, Depends(get_reviews)]
ObjectsDep = Annotated[ObjectStore, Depends(get_objects)]


class Staff(BaseModel):
    user_id: int
    name: str
    course_id: int
    quiz_id: int
    caps: set[str]

    @property
    def actor(self) -> str:
        return f"moodle:{self.user_id}"

    def require(self, cap: str) -> None:
        if cap not in self.caps:
            raise error(403, "forbidden", f"this action needs the {cap} capability")


async def current_staff(settings: SettingsDep, authorization: Annotated[str | None, Header()] = None) -> Staff:
    if not authorization or not authorization.startswith("Bearer "):
        raise error(401, "unauthorized", "staff token required")
    try:
        claims = decode_staff_token(authorization.removeprefix("Bearer "), settings)
    except TokenError as exc:
        raise error(401, "unauthorized", "invalid staff token") from exc
    return Staff(
        user_id=int(claims["sub"]),
        name=str(claims.get("name", "")),
        course_id=int(claims["course_id"]),
        quiz_id=int(claims["quiz_id"]),
        caps=set(claims["caps"]),
    )


StaffDep = Annotated[Staff, Depends(current_staff)]


def in_scope(staff: Staff, quiz_id: int) -> None:
    if quiz_id != staff.quiz_id:
        raise error(403, "forbidden", "token is for a different quiz")


async def scoped_session(session_id: str, staff: StaffDep, store: StoreDep) -> Session:
    session = await store.get_session(session_id)
    # Same answer for "missing" and "other quiz", so ids cannot be probed across quizzes.
    if session is None or session.quiz_id != staff.quiz_id or session.course_id != staff.course_id:
        raise error(404, "not_found", "session not found")
    return session


SessionDep = Annotated[Session, Depends(scoped_session)]


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)


@router.get("/quizzes/{quiz_id}/sessions")
async def list_sessions(
    quiz_id: int,
    staff: StaffDep,
    reviews: ReviewsDep,
    after: str | None = None,
    limit: Annotated[int, Query(ge=1, le=PAGE)] = 100,
) -> dict[str, Any]:
    staff.require("review")
    in_scope(staff, quiz_id)
    rows = await reviews.list_sessions(quiz_id, after, limit)
    return {
        "sessions": [r.to_json() for r in rows],
        "next": rows[-1].session.id if len(rows) == limit else None,
    }


@router.get("/quizzes/{quiz_id}/summary")
async def summary(quiz_id: int, staff: StaffDep, reviews: ReviewsDep) -> dict[str, Any]:
    staff.require("review")
    in_scope(staff, quiz_id)
    return await reviews.summary(quiz_id)


def public_analysis(analysis: dict[str, Any] | None) -> dict[str, Any] | None:
    """Analysis without the face embedding: reviewers need the facts, not biometric vectors."""
    if analysis is None:
        return None
    return {k: v for k, v in analysis.items() if k != "embedding"}


@router.get("/sessions/{session_id}")
async def session_review(
    session: SessionDep,
    staff: StaffDep,
    reviews: ReviewsDep,
    objects: ObjectsDep,
    settings: SettingsDep,
    request: Request,
) -> dict[str, Any]:
    staff.require("review")
    uploads = await reviews.uploads(session.id)
    purged = session.purged_at is not None
    for u in uploads:
        u["analysis"] = public_analysis(u["analysis"])
        u["url"] = None if purged else objects.presign_get(u["key"], settings.evidence_view_ttl_s)
    await reviews.audit(staff.actor, "view_evidence", session.id, client_ip(request), {"uploads": len(uploads)})
    return {
        "session": {
            "session_id": session.id,
            "moodle_user_id": session.moodle_user_id,
            "status": session.status,
            "policy": session.policy,
            "precheck": session.precheck,
            "consent_version": session.consent_version,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "client_health": session.client_health,
            "legal_hold": session.legal_hold,
            "purged": purged,
        },
        "score": await reviews.score(session.id),
        "flags": await reviews.flags(session.id),
        "uploads": uploads,
        "events": await reviews.events(session.id),
        "reviews": [r.to_json() for r in await reviews.reviews(session.id)],
        "url_ttl_s": settings.evidence_view_ttl_s,
    }


class DecisionRequest(BaseModel):
    decision: Literal["no_issue", "concern", "refer_misconduct"]
    notes: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def reasons_for_concerns(self) -> "DecisionRequest":
        if self.decision != "no_issue" and not self.notes.strip():
            raise ValueError("notes are required when raising a concern or referring a case")
        return self


class AppealRequest(BaseModel):
    status: Literal["opened", "upheld", "overturned", "withdrawn"]
    notes: str = Field(min_length=1, max_length=4000)


async def record(
    kind: str,
    value: str,
    notes: str,
    session: Session,
    staff: Staff,
    reviews: ReviewStore,
    store: Any,
    request: Request,
) -> dict[str, Any]:
    review = Review(
        session_id=session.id,
        kind=kind,
        value=value,
        notes=notes.strip(),
        reviewer_id=staff.user_id,
        reviewer_name=staff.name,
    )
    await reviews.add_review(review)
    await reviews.audit(staff.actor, f"record_{kind}", session.id, client_ip(request), {"value": value})
    await store.enqueue(
        "decision.recorded",
        {
            "session_id": session.id,
            "moodle_user_id": session.moodle_user_id,
            "quiz_id": session.quiz_id,
            "kind": kind,
            "value": value,
            "reviewer_id": staff.user_id,
        },
    )
    return review.to_json()


@router.post("/sessions/{session_id}/decision")
async def decide(
    body: DecisionRequest,
    session: SessionDep,
    staff: StaffDep,
    reviews: ReviewsDep,
    store: StoreDep,
    request: Request,
) -> dict[str, Any]:
    staff.require("decide")
    assert body.decision in DECISIONS
    return await record("decision", body.decision, body.notes, session, staff, reviews, store, request)


@router.post("/sessions/{session_id}/appeal")
async def appeal(
    body: AppealRequest,
    session: SessionDep,
    staff: StaffDep,
    reviews: ReviewsDep,
    store: StoreDep,
    request: Request,
) -> dict[str, Any]:
    staff.require("decide")
    assert body.status in APPEALS
    return await record("appeal", body.status, body.notes, session, staff, reviews, store, request)


CSV_COLUMNS = [
    "session_id",
    "moodle_user_id",
    "status",
    "started_at",
    "ended_at",
    "integrity_score",
    "band",
    "flag_count",
    "camera_images",
    "screen_images",
    "decision",
    "appeal",
]


@router.get("/quizzes/{quiz_id}/export.csv")
async def export_csv(quiz_id: int, staff: StaffDep, reviews: ReviewsDep, request: Request) -> StreamingResponse:
    staff.require("exportevidence")
    in_scope(staff, quiz_id)
    await reviews.audit(staff.actor, "export_csv", f"quiz:{quiz_id}", client_ip(request), {})

    async def rows() -> AsyncIterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(CSV_COLUMNS)
        after = None
        while True:
            page = await reviews.list_sessions(quiz_id, after, PAGE)
            for r in page:
                j = r.to_json()
                writer.writerow(
                    [j[c] for c in CSV_COLUMNS[:8]]
                    + [r.uploads.get("camera", 0), r.uploads.get("screen", 0), j["decision"] or "", j["appeal"] or ""]
                )
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate()
            if len(page) < PAGE:
                return
            after = page[-1].session.id

    return StreamingResponse(
        rows(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="examproctor-quiz-{quiz_id}.csv"'},
    )
