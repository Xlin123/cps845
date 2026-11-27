from datetime import date as date_type
from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from app.auth import require_role
from app.clock import CLUB_TIMEZONE, Clock, get_clock
from app.db import get_db
from app.models import Profile, Role
from app.sessions import (
    Collision,
    CollisionChangedError,
    DeleteRejectedError,
    DeleteTooManyError,
    SessionValidationError,
    as_aware,
    create_session,
    delete_sessions,
    list_not_started,
    to_utc_start,
    validate_length,
    validate_price_cents,
    validate_start,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
require_coach = require_role(Role.coach)


class CreateSessionRequest(BaseModel):
    date: str
    start_time: str
    length_minutes: int = 60
    price: float
    overwrite_ids: list[int] | None = None


class DeleteSessionsRequest(BaseModel):
    session_ids: list[int]


class SessionResponse(BaseModel):
    id: int
    start: str
    length_minutes: int
    price: float


class CollisionInfo(BaseModel):
    id: int
    start: str
    length_minutes: int


class CollisionResponse(BaseModel):
    detail: str
    can_overwrite: bool
    collisions: list[CollisionInfo]


def _local_label(start: datetime) -> str:
    local = start.astimezone(CLUB_TIMEZONE)
    return f"{local:%Y-%m-%d %H:%M}"


def _collision_response(collisions: list[Collision], *, changed: bool) -> CollisionResponse:
    can_overwrite = not any(c.in_progress for c in collisions)
    names = ", ".join(_local_label(c.start) for c in collisions)
    if not can_overwrite:
        detail = "This collides with the session in progress. You can only cancel."
    elif changed:
        detail = f"The colliding sessions have changed: {names}. Overwrite or cancel?"
    else:
        detail = f"This collides with the session on {names}. Overwrite or cancel?"
    return CollisionResponse(
        detail=detail,
        can_overwrite=can_overwrite,
        collisions=[
            CollisionInfo(id=c.id, start=c.start.isoformat(), length_minutes=c.length_minutes)
            for c in collisions
        ],
    )


def _delete_rejected_detail(exc: DeleteRejectedError) -> dict:
    reasons = []
    if exc.started:
        labels = ", ".join(_local_label(c.start) for c in exc.started)
        reasons.append(f"already started: {labels}")
    if exc.missing_ids:
        reasons.append(f"no longer exists: {', '.join(str(i) for i in exc.missing_ids)}")
    return {
        "detail": "Nothing was deleted; " + "; ".join(reasons),
        "missing_ids": exc.missing_ids,
        "started": [{"id": c.id, "start": c.start.isoformat()} for c in exc.started],
    }


@router.get("", response_model=list[SessionResponse])
def list_upcoming(
    coach: Profile = Depends(require_coach),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> list[SessionResponse]:
    sessions = list_not_started(db, now=clock.now())
    return [
        SessionResponse(
            id=s.id,
            start=as_aware(s.start).isoformat(),
            length_minutes=s.length_minutes,
            price=round(s.price_cents / 100, 2),
        )
        for s in sessions
    ]


@router.delete("", status_code=204)
def delete(
    body: DeleteSessionsRequest,
    coach: Profile = Depends(require_coach),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> None:
    try:
        delete_sessions(db, session_ids=body.session_ids, deleted_by=coach.id, clock=clock)
    except DeleteTooManyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DeleteRejectedError as exc:
        raise HTTPException(status_code=409, detail=_delete_rejected_detail(exc)) from exc
    db.commit()


@router.post("", response_model=SessionResponse, status_code=201)
def create(
    body: CreateSessionRequest,
    coach: Profile = Depends(require_coach),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> SessionResponse:
    try:
        on = date_type.fromisoformat(body.date)
        at = time.fromisoformat(body.start_time)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date or time") from exc

    start = to_utc_start(on, at)

    try:
        validate_length(body.length_minutes)
        price_cents = validate_price_cents(body.price)
        validate_start(start, clock=clock)
    except SessionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        session = create_session(
            db,
            start=start,
            length_minutes=body.length_minutes,
            price_cents=price_cents,
            created_by=coach.id,
            overwrite_ids=body.overwrite_ids,
            clock=clock,
        )
    except CollisionChangedError as exc:
        changed = body.overwrite_ids is not None
        response = _collision_response(exc.colliding, changed=changed)
        raise HTTPException(status_code=409, detail=response.model_dump()) from exc

    return SessionResponse(
        id=session.id,
        start=as_aware(session.start).isoformat(),
        length_minutes=session.length_minutes,
        price=round(session.price_cents / 100, 2),
    )
