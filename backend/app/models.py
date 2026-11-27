import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Role(enum.StrEnum):
    customer = "customer"
    coach = "coach"
    treasurer = "treasurer"


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    # Stored lower-cased so the unique constraint is case-insensitive.
    email: Mapped[str] = mapped_column(String(254), unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(Enum(Role))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SignInSession(Base):
    __tablename__ = "sign_in_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FailedAttempt(Base):
    """A failed sign-in or coach-code attempt, for the per-address throttle."""

    __tablename__ = "failed_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    client_address: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ClassSession(Base):
    """A bookable class the club runs at its one venue."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    length_minutes: Mapped[int] = mapped_column(Integer)
    price_cents: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[int] = mapped_column(ForeignKey("profiles.id"))


class NoticeKind(enum.StrEnum):
    created = "created"
    deleted = "deleted"


class SessionNotice(Base):
    """A queued notice about a session being created or deleted.

    Fields are a snapshot of the session at queue time, since a deleted
    session's row no longer exists by the time the notice is sent.
    """

    __tablename__ = "session_notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[NoticeKind] = mapped_column(Enum(NoticeKind))
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"), nullable=True)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    length_minutes: Mapped[int] = mapped_column(Integer)
    price_cents: Mapped[int] = mapped_column(Integer)


class CheckIn(Base):
    """A member's check-in to the session in progress."""

    __tablename__ = "check_ins"
    __table_args__ = (
        UniqueConstraint("profile_id", "session_id", name="uq_check_ins_profile_session"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    checked_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    price_cents: Mapped[int] = mapped_column(Integer)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SessionDeletion(Base):
    """A log entry for a deleted session, naming who deleted it and when."""

    __tablename__ = "session_deletions"

    id: Mapped[int] = mapped_column(primary_key=True)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    length_minutes: Mapped[int] = mapped_column(Integer)
    price_cents: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    deleted_by: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
