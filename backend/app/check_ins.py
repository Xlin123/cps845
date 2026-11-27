"""Check-in window and the check-in rule.

Shared by the Check In endpoint. At most one session is in progress at a
time, since the club has one venue and sessions never overlap.
"""

from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.clock import Clock
from app.models import CheckIn, ClassSession, Profile, Role
from app.sessions import as_aware

CHECK_IN_WINDOW_BEFORE = timedelta(minutes=15)


class NoSessionInProgressError(ValueError):
    """No session is in its check-in window right now."""


class AlreadyCheckedInError(ValueError):
    """The profile already checked in to the session in progress."""


def find_session_in_progress(db: DbSession, *, now: datetime) -> ClassSession | None:
    """The session whose check-in window covers `now`, if any."""
    for session in db.query(ClassSession).all():
        start = as_aware(session.start)
        window_start = start - CHECK_IN_WINDOW_BEFORE
        end = start + timedelta(minutes=session.length_minutes)
        if window_start <= now < end:
            return session
    return None


def check_in(db: DbSession, *, profile: Profile, clock: Clock) -> CheckIn:
    """Check the profile in to the session in progress.

    Raises NoSessionInProgressError if there is no session to check in to,
    or AlreadyCheckedInError if the profile already checked in to it. The
    unique profile+session constraint is the source of truth for the
    latter, so two simultaneous check-ins by one member leave exactly one
    row.
    """
    now = clock.now()
    session = find_session_in_progress(db, now=now)
    if session is None:
        raise NoSessionInProgressError("There is no session to check in to right now")

    existing = db.query(CheckIn).filter_by(profile_id=profile.id, session_id=session.id).first()
    if existing is not None:
        raise AlreadyCheckedInError("You have already checked in to this session")

    price_cents = session.price_cents if profile.role == Role.customer else 0
    record = CheckIn(
        profile_id=profile.id,
        session_id=session.id,
        checked_in_at=now,
        price_cents=price_cents,
        paid_at=None,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AlreadyCheckedInError("You have already checked in to this session") from None
    db.refresh(record)
    return record


def sessions_attended(db: DbSession, *, profile_id: int) -> int:
    return db.query(CheckIn).filter_by(profile_id=profile_id).count()
