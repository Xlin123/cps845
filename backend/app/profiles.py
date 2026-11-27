"""Create Profile: sign-up, confirmation and the pending-profile sweep.

Touches cryptography (confirmation tokens, coach-code comparison): flagged
for human review.
"""

import hmac
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.clock import Clock
from app.models import ConfirmationToken, Outbox, Profile, Role
from app.security import hash_password, hash_token, new_session_token

NAME_MIN = 1
NAME_MAX = 100
EMAIL_MAX = 254
PASSWORD_MIN = 12
PASSWORD_MAX = 128
PHONE_MIN_DIGITS = 7
PHONE_MAX_DIGITS = 15
PENDING_EXPIRY = timedelta(days=4)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_ALLOWED_RE = re.compile(r"^\+?[0-9 \-()]*$")


class ProfileValidationError(ValueError):
    """A sign-up field is out of bounds."""


class CoachCodeWrongError(ValueError):
    """The coach code did not match, or none is configured."""


def _as_aware(dt: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip; treat naive timestamps as UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def validate_name(name: str) -> None:
    if not (NAME_MIN <= len(name) <= NAME_MAX):
        raise ProfileValidationError("Enter a name of 1 to 100 characters")


def validate_email(email: str) -> None:
    if len(email) > EMAIL_MAX or not _EMAIL_RE.match(email):
        raise ProfileValidationError("Enter a valid email address")


def validate_password(password: str) -> None:
    if not (PASSWORD_MIN <= len(password) <= PASSWORD_MAX):
        raise ProfileValidationError("Use a password of 12 to 128 characters")


def validate_phone(phone: str) -> None:
    digit_count = sum(1 for ch in phone if ch.isdigit())
    if not _PHONE_ALLOWED_RE.match(phone) or not (
        PHONE_MIN_DIGITS <= digit_count <= PHONE_MAX_DIGITS
    ):
        raise ProfileValidationError("Enter a phone number of 7 to 15 digits")


def _role_for_coach_code(coach_code: str | None) -> Role:
    if coach_code is None:
        return Role.customer
    configured = os.environ.get("CM_COACH_CODE")
    if not configured or not hmac.compare_digest(coach_code, configured):
        raise CoachCodeWrongError("That coach code is not right")
    return Role.coach


@dataclass
class SignUpResult:
    created: bool


def sign_up(
    db: DbSession,
    *,
    name: str,
    email: str,
    phone: str | None,
    password: str,
    coach_code: str | None,
    clock: Clock,
) -> SignUpResult:
    """Create a pending profile and queue its confirmation email.

    A sign-up for an address that already has a profile (pending or
    confirmed) changes nothing and reports the same result, so sign-up
    never reveals who is a member.
    """
    validate_name(name)
    validate_email(email)
    validate_password(password)
    if phone is not None:
        validate_phone(phone)
    role = _role_for_coach_code(coach_code)

    normalized_email = email.lower()
    now = clock.now()

    if db.query(Profile).filter_by(email=normalized_email).first() is not None:
        return SignUpResult(created=False)

    profile = Profile(
        name=name,
        email=normalized_email,
        phone=phone,
        password_hash=hash_password(password),
        role=role,
        confirmed_at=None,
        created_at=now,
    )
    db.add(profile)
    try:
        db.flush()
    except IntegrityError:
        # Another request won the race to create this email; same answer.
        db.rollback()
        return SignUpResult(created=False)

    token = new_session_token()
    db.add(
        ConfirmationToken(
            profile_id=profile.id,
            token_hash=hash_token(token),
            expires_at=now + PENDING_EXPIRY,
        )
    )
    db.add(
        Outbox(
            to=normalized_email,
            subject="Confirm your profile",
            body=f"Follow this link to confirm your profile: /confirm?token={token}",
            created_at=now,
        )
    )
    db.commit()
    return SignUpResult(created=True)


class ConfirmationInvalidError(ValueError):
    """The confirmation link is wrong, used, or expired."""


def confirm(db: DbSession, *, token: str, clock: Clock) -> None:
    record = db.query(ConfirmationToken).filter_by(token_hash=hash_token(token)).first()
    if record is None or _as_aware(record.expires_at) <= clock.now():
        raise ConfirmationInvalidError("This link has already been used or has expired")

    profile = db.get(Profile, record.profile_id)
    db.delete(record)
    if profile is not None:
        profile.confirmed_at = clock.now()
    db.commit()


def sweep_pending_profiles(db: DbSession, *, clock: Clock) -> int:
    """Delete pending profiles whose sign-up is older than 4 days."""
    cutoff = clock.now() - PENDING_EXPIRY
    stale = (
        db.query(Profile).filter(Profile.confirmed_at.is_(None), Profile.created_at < cutoff).all()
    )
    for profile in stale:
        db.query(ConfirmationToken).filter_by(profile_id=profile.id).delete()
        db.delete(profile)
    db.commit()
    return len(stale)
