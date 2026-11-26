from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.clock import Clock, get_clock
from app.db import get_db
from app.models import FailedAttempt, Profile, Role, SignInSession
from app.security import hash_token

SESSION_COOKIE = "session"
SESSION_LIFETIME = timedelta(days=7)
THROTTLE_WINDOW = timedelta(minutes=15)
THROTTLE_LIMIT = 10


def _as_aware(dt: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip; treat naive timestamps as UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def landing_for(role: Role) -> str:
    return "club_finances" if role is Role.treasurer else "main_menu"


def client_address(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def is_throttled(db: Session, *, kind: str, address: str, clock: Clock) -> bool:
    cutoff = clock.now() - THROTTLE_WINDOW
    count = (
        db.query(FailedAttempt)
        .filter(
            FailedAttempt.kind == kind,
            FailedAttempt.client_address == address,
            FailedAttempt.occurred_at >= cutoff,
        )
        .count()
    )
    return count >= THROTTLE_LIMIT


def record_failure(db: Session, *, kind: str, address: str, clock: Clock) -> None:
    db.add(FailedAttempt(kind=kind, client_address=address, occurred_at=clock.now()))
    db.commit()


def get_current_profile(
    request: Request,
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Profile:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in")

    session = db.query(SignInSession).filter_by(token_hash=hash_token(token)).first()
    if session is None or _as_aware(session.expires_at) <= clock.now():
        raise HTTPException(status_code=401, detail="Not signed in")

    profile = db.get(Profile, session.profile_id)
    if profile is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return profile


def require_role(*roles: Role) -> Callable[[Profile], Profile]:
    allowed: Iterable[Role] = roles

    def checker(profile: Profile = Depends(get_current_profile)) -> Profile:
        if profile.role not in allowed:
            raise HTTPException(status_code=403, detail="Forbidden")
        return profile

    return checker
