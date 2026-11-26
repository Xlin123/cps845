from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.cli import TreasurerExistsError, create_treasurer
from app.models import Profile, Role
from app.security import hash_password

from .conftest import FakeClock, scenario


def _make_profile(
    db_session: Session,
    *,
    email: str,
    password: str,
    role: Role = Role.customer,
    confirmed: bool,
    now,
) -> Profile:
    profile = Profile(
        name="Member",
        email=email.lower(),
        phone=None,
        password_hash=hash_password(password),
        role=role,
        confirmed_at=now if confirmed else None,
    )
    db_session.add(profile)
    db_session.commit()
    return profile


@scenario("A pending profile cannot sign in")
def test_pending_profile_cannot_sign_in(client, db_session, clock):
    _make_profile(
        db_session,
        email="pat@example.com",
        password="pending passphrase",
        confirmed=False,
        now=clock.now(),
    )

    response = client.post(
        "/api/auth/sign-in", json={"email": "pat@example.com", "password": "pending passphrase"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Confirm your email address before signing in"


@scenario("A wrong password and an unknown email address get the same refusal")
def test_wrong_password_and_unknown_email_same_refusal(client, db_session, clock):
    _make_profile(
        db_session,
        email="cara@example.com",
        password="correct horse battery",
        confirmed=True,
        now=clock.now(),
    )

    wrong_password = client.post(
        "/api/auth/sign-in", json={"email": "cara@example.com", "password": "wrong passphrase"}
    )
    unknown_email = client.post(
        "/api/auth/sign-in", json={"email": "nobody@example.com", "password": "wrong passphrase"}
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]
    assert wrong_password.json()["detail"] == "Email address or password is wrong"


@scenario("Signing out ends the session")
def test_sign_out_ends_the_session(client, db_session, clock):
    _make_profile(
        db_session,
        email="cara@example.com",
        password="correct horse battery",
        confirmed=True,
        now=clock.now(),
    )

    sign_in = client.post(
        "/api/auth/sign-in", json={"email": "cara@example.com", "password": "correct horse battery"}
    )
    token = sign_in.cookies.get("session")

    client.post("/api/auth/sign-out")

    response = client.get("/api/auth/me", cookies={"session": token})

    assert response.status_code == 401


@scenario("A session expires 7 days after sign-in")
def test_session_expires_after_seven_days(client, db_session, clock: FakeClock):
    _make_profile(
        db_session,
        email="cara@example.com",
        password="correct horse battery",
        confirmed=True,
        now=clock.now(),
    )

    sign_in = client.post(
        "/api/auth/sign-in", json={"email": "cara@example.com", "password": "correct horse battery"}
    )
    token = sign_in.cookies.get("session")

    clock.advance(timedelta(days=7, minutes=1))

    response = client.get("/api/auth/me", cookies={"session": token})

    assert response.status_code == 401


@scenario("A request with a made-up session cookie is treated as signed out")
def test_forged_session_cookie_is_treated_as_signed_out(client):
    response = client.get("/api/auth/me", cookies={"session": "a" * 64})

    assert response.status_code == 401


@scenario("Failed sign-ins from one client address are throttled")
def test_failed_sign_ins_from_one_address_are_throttled(client_factory, db_session, clock):
    _make_profile(
        db_session,
        email="cara@example.com",
        password="correct horse battery",
        confirmed=True,
        now=clock.now(),
    )
    attacker = client_factory("203.0.113.5")
    for _ in range(10):
        attacker.post("/api/auth/sign-in", json={"email": "cara@example.com", "password": "wrong"})

    response = attacker.post(
        "/api/auth/sign-in", json={"email": "cara@example.com", "password": "correct horse battery"}
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Too many attempts. Try again later"


@scenario("Sign-ins from another client address are not throttled")
def test_sign_ins_from_another_address_are_not_throttled(client_factory, db_session, clock):
    _make_profile(
        db_session,
        email="cara@example.com",
        password="correct horse battery",
        confirmed=True,
        now=clock.now(),
    )
    attacker = client_factory("203.0.113.5")
    for _ in range(10):
        attacker.post("/api/auth/sign-in", json={"email": "cara@example.com", "password": "wrong"})

    other = client_factory("198.51.100.9")
    response = other.post(
        "/api/auth/sign-in", json={"email": "cara@example.com", "password": "correct horse battery"}
    )

    assert response.status_code == 200
    assert response.json()["landing"] == "main_menu"


@scenario("The Treasurer is created with the server command")
def test_treasurer_is_created_with_the_server_command(db_session, clock):
    profile = create_treasurer(
        db_session, "Tess Okafor", "tess@example.com", "treasurer passphrase", clock.now()
    )

    assert profile.role is Role.treasurer
    assert profile.confirmed_at is not None
    stored = db_session.query(Profile).filter_by(email="tess@example.com").one()
    assert stored.role is Role.treasurer


@scenario("A second Treasurer cannot be created")
def test_second_treasurer_cannot_be_created(db_session, clock):
    create_treasurer(
        db_session, "Tess Okafor", "tess@example.com", "treasurer passphrase", clock.now()
    )

    with pytest.raises(TreasurerExistsError, match="A Treasurer already exists"):
        create_treasurer(
            db_session, "Mallory", "mallory@example.com", "whatever password", clock.now()
        )

    assert db_session.query(Profile).filter_by(email="mallory@example.com").first() is None


def test_require_role_rejects_the_wrong_role():
    from fastapi import HTTPException

    from app.auth import require_role

    checker = require_role(Role.treasurer)
    customer = Profile(
        name="Cara", email="cara@example.com", phone=None, password_hash="x", role=Role.customer
    )

    with pytest.raises(HTTPException) as exc_info:
        checker(profile=customer)

    assert exc_info.value.status_code == 403


def test_require_role_accepts_the_right_role():
    from app.auth import require_role

    checker = require_role(Role.treasurer)
    treasurer = Profile(
        name="Tess", email="tess@example.com", phone=None, password_hash="x", role=Role.treasurer
    )

    assert checker(profile=treasurer) is treasurer
