from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from app.auth import require_role
from app.check_ins import (
    AlreadyCheckedInError,
    NoSessionInProgressError,
    check_in,
    sessions_attended,
)
from app.clock import Clock, get_clock
from app.db import get_db
from app.models import ClassSession, Profile, Role
from app.sessions import as_aware

router = APIRouter(prefix="/api/check-ins", tags=["check-ins"])
require_member = require_role(Role.customer, Role.coach)


class AttendanceResponse(BaseModel):
    sessions_attended: int


class CheckInResponse(BaseModel):
    session_start: str
    checked_in_at: str
    price: float
    sessions_attended: int


@router.get("/me", response_model=AttendanceResponse)
def me(
    profile: Profile = Depends(require_member),
    db: DbSession = Depends(get_db),
) -> AttendanceResponse:
    return AttendanceResponse(sessions_attended=sessions_attended(db, profile_id=profile.id))


@router.post("", response_model=CheckInResponse, status_code=201)
def create(
    profile: Profile = Depends(require_member),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> CheckInResponse:
    try:
        record = check_in(db, profile=profile, clock=clock)
    except NoSessionInProgressError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AlreadyCheckedInError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    session = db.get(ClassSession, record.session_id)
    assert session is not None
    return CheckInResponse(
        session_start=as_aware(session.start).isoformat(),
        checked_in_at=as_aware(record.checked_in_at).isoformat(),
        price=round(record.price_cents / 100, 2),
        sessions_attended=sessions_attended(db, profile_id=profile.id),
    )
