"""Session bounds, collision and deletion rules.

Shared by the Create Session endpoint and (later) Session Deleted, so both
go through the same all-or-nothing delete and the same collision check.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.orm import Session as DbSession

from app.clock import CLUB_TIMEZONE, Clock
from app.models import ClassSession, NoticeKind, SessionDeletion, SessionNotice

MIN_LENGTH_MINUTES = 15
MAX_LENGTH_MINUTES = 480
MIN_PRICE_CENTS = 0
MAX_PRICE_CENTS = 100_000
MAX_START_DAYS_AHEAD = 365
MAX_SESSIONS_PER_DELETE = 100


def as_aware(dt: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip; treat naive timestamps as UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


class SessionValidationError(ValueError):
    """A Create Session field is out of bounds."""


class CollisionChangedError(ValueError):
    """The colliding sessions shown to the Coach are no longer current."""

    def __init__(self, colliding: list["Collision"]) -> None:
        super().__init__("The colliding sessions have changed")
        self.colliding = colliding


class DeleteRejectedError(ValueError):
    """A session in the requested delete has started or no longer exists."""


def to_utc_start(on: date, at: time) -> datetime:
    """Combine a club-local date and time into a UTC-aware datetime."""
    local = datetime.combine(on, at, tzinfo=CLUB_TIMEZONE)
    return local.astimezone(UTC)


def validate_price_cents(dollars: float) -> int:
    cents = round(dollars * 100)
    if abs(cents - dollars * 100) > 1e-6 or cents < MIN_PRICE_CENTS or cents > MAX_PRICE_CENTS:
        raise SessionValidationError("A price is 0.00 to 1,000.00")
    return cents


def validate_length(length_minutes: int) -> None:
    if length_minutes < MIN_LENGTH_MINUTES or length_minutes > MAX_LENGTH_MINUTES:
        raise SessionValidationError("A session lasts 15 to 480 minutes")


def validate_start(start: datetime, *, clock: Clock) -> None:
    now = clock.now()
    if start <= now:
        raise SessionValidationError("A session must start in the future")
    if start > now + timedelta(days=MAX_START_DAYS_AHEAD):
        raise SessionValidationError("A session must start within 365 days")


@dataclass
class Collision:
    id: int
    start: datetime
    length_minutes: int
    in_progress: bool


def find_collisions(
    db: DbSession, *, start: datetime, length_minutes: int, now: datetime
) -> list[Collision]:
    """Sessions not yet ended that overlap [start, start + length_minutes)."""
    end = start + timedelta(minutes=length_minutes)
    collisions = []
    for session in db.query(ClassSession).all():
        session_start = as_aware(session.start)
        session_end = session_start + timedelta(minutes=session.length_minutes)
        if session_end <= now:
            continue
        if session_start < end and start < session_end:
            collisions.append(
                Collision(
                    id=session.id,
                    start=session_start,
                    length_minutes=session.length_minutes,
                    in_progress=session_start <= now,
                )
            )
    return collisions


def delete_sessions(
    db: DbSession, *, session_ids: list[int], deleted_by: int, clock: Clock
) -> None:
    """Delete sessions, all or nothing. Stages changes; caller commits.

    Future sessions only. Drops an unsent created-notice for a deleted
    session, or queues a deleted-notice if none was pending.
    """
    if len(session_ids) > MAX_SESSIONS_PER_DELETE:
        raise DeleteRejectedError(f"At most {MAX_SESSIONS_PER_DELETE} sessions per delete")

    now = clock.now()
    sessions = db.query(ClassSession).filter(ClassSession.id.in_(session_ids)).all()
    found_ids = {s.id for s in sessions}
    missing = set(session_ids) - found_ids
    if missing:
        raise DeleteRejectedError(f"No longer exists: {sorted(missing)}")
    started = [s.id for s in sessions if as_aware(s.start) <= now]
    if started:
        raise DeleteRejectedError(f"Already started: {sorted(started)}")

    for session in sessions:
        pending_created = (
            db.query(SessionNotice)
            .filter(
                SessionNotice.kind == NoticeKind.created,
                SessionNotice.session_id == session.id,
            )
            .first()
        )
        if pending_created is not None:
            db.delete(pending_created)
        else:
            db.add(
                SessionNotice(
                    kind=NoticeKind.deleted,
                    session_id=None,
                    start=session.start,
                    length_minutes=session.length_minutes,
                    price_cents=session.price_cents,
                )
            )
        db.add(
            SessionDeletion(
                start=session.start,
                length_minutes=session.length_minutes,
                price_cents=session.price_cents,
                created_by=session.created_by,
                deleted_by=deleted_by,
                deleted_at=now,
            )
        )
        db.delete(session)


def create_session(
    db: DbSession,
    *,
    start: datetime,
    length_minutes: int,
    price_cents: int,
    created_by: int,
    overwrite_ids: list[int] | None,
    clock: Clock,
) -> ClassSession:
    """Create a session, handling collisions and overwrite in one transaction."""
    now = clock.now()
    collisions = find_collisions(db, start=start, length_minutes=length_minutes, now=now)

    if collisions and overwrite_ids is None:
        raise CollisionChangedError(collisions)

    if collisions:
        current_ids = sorted(c.id for c in collisions)
        if any(c.in_progress for c in collisions) or current_ids != sorted(overwrite_ids):
            raise CollisionChangedError(collisions)
        delete_sessions(db, session_ids=overwrite_ids, deleted_by=created_by, clock=clock)

    session = ClassSession(
        start=start, length_minutes=length_minutes, price_cents=price_cents, created_by=created_by
    )
    db.add(session)
    db.flush()
    db.add(
        SessionNotice(
            kind=NoticeKind.created,
            session_id=session.id,
            start=session.start,
            length_minutes=session.length_minutes,
            price_cents=session.price_cents,
        )
    )
    db.commit()
    db.refresh(session)
    return session
