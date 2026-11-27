from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.models import ConfirmationToken, Outbox, Profile, Role
from app.profiles import sweep_pending_profiles

from .conftest import FakeClock, scenario

COACH_CODE = "TEST-COACH-CODE"


@pytest.fixture(autouse=True)
def coach_code(monkeypatch):
    monkeypatch.setenv("CM_COACH_CODE", COACH_CODE)


def _sign_up(
    client,
    *,
    email="cara@example.com",
    name="Cara Diaz",
    phone="416-555-0101",
    password="correct horse battery",
    coach_code=None,
    address="testclient",
):
    return client.post(
        "/api/profiles/sign-up",
        json={
            "name": name,
            "email": email,
            "phone": phone,
            "password": password,
            "coach_code": coach_code,
        },
    )


def _confirmation_token(db_session: Session, email: str) -> str:
    """Tests cannot read the mailed token, so they take it from the outbox body."""
    outbox_entry = db_session.query(Outbox).filter_by(to=email.lower()).one()
    return outbox_entry.body.rsplit("token=", 1)[1]


@scenario("A visitor creates a Customer profile and is sent a confirmation link")
def test_sign_up_creates_pending_customer_and_outbox_email(client, db_session):
    response = _sign_up(client)

    assert response.status_code == 200
    assert response.json()["message"] == "Check your email for a confirmation link"
    profile = db_session.query(Profile).filter_by(email="cara@example.com").one()
    assert profile.role is Role.customer
    assert profile.confirmed_at is None
    outbox = db_session.query(Outbox).filter_by(to="cara@example.com").all()
    assert len(outbox) == 1


@scenario("Following the confirmation link activates the profile")
def test_confirming_activates_the_profile(client, db_session, clock: FakeClock):
    _sign_up(client)
    token = _confirmation_token(db_session, "cara@example.com")

    clock.advance(timedelta(days=1))
    response = client.post("/api/profiles/confirm", json={"token": token})

    assert response.status_code == 200
    profile = db_session.query(Profile).filter_by(email="cara@example.com").one()
    assert profile.confirmed_at is not None

    sign_in = client.post(
        "/api/auth/sign-in", json={"email": "cara@example.com", "password": "correct horse battery"}
    )
    assert sign_in.status_code == 200


@scenario("An improperly formatted email address is refused")
@pytest.mark.parametrize(
    "email",
    ["cara.example.com", "cara@", "@example.com", "cara@example", "cara@@example.com"],
)
def test_improperly_formatted_email_is_refused(client, db_session, email):
    response = _sign_up(client, email=email)

    assert response.status_code == 422
    assert response.json()["detail"] == "Enter a valid email address"
    assert db_session.query(Profile).count() == 0


@scenario("An invalid password is refused")
@pytest.mark.parametrize("length", [0, 11, 129])
def test_invalid_password_length_is_refused(client, db_session, length):
    response = _sign_up(client, password="a" * length)

    assert response.status_code == 422
    assert response.json()["detail"] == "Use a password of 12 to 128 characters"
    assert db_session.query(Profile).count() == 0


@scenario("An invalid phone number is refused")
@pytest.mark.parametrize("phone", ["555-01", "1234567890123456", "call me"])
def test_invalid_phone_is_refused(client, db_session, phone):
    response = _sign_up(client, phone=phone)

    assert response.status_code == 422
    assert response.json()["detail"] == "Enter a phone number of 7 to 15 digits"
    assert db_session.query(Profile).count() == 0


@scenario("A visitor with the coach code creates a Coach profile")
def test_sign_up_with_coach_code_creates_coach_profile(client, db_session):
    response = _sign_up(client, email="colm@example.com", name="Colm Byrne", coach_code=COACH_CODE)

    assert response.status_code == 200
    profile = db_session.query(Profile).filter_by(email="colm@example.com").one()
    assert profile.role is Role.coach
    assert profile.confirmed_at is None


@scenario("A wrong coach code is refused and creates no profile")
def test_wrong_coach_code_is_refused(client, db_session):
    response = _sign_up(client, email="colm@example.com", coach_code="WRONG-CODE")

    assert response.status_code == 422
    assert response.json()["detail"] == "That coach code is not right"
    assert db_session.query(Profile).count() == 0


@scenario("With no coach code set, no Coach profile can be created")
def test_no_coach_code_configured_refuses_coach_sign_up(client, db_session, monkeypatch):
    monkeypatch.delenv("CM_COACH_CODE", raising=False)

    response = _sign_up(client, email="colm@example.com", coach_code=COACH_CODE)

    assert response.status_code == 422
    assert response.json()["detail"] == "That coach code is not right"
    assert db_session.query(Profile).count() == 0


@scenario("A sign-up that names a role still gets a Customer profile")
def test_sign_up_ignores_a_named_role(client, db_session):
    response = client.post(
        "/api/profiles/sign-up",
        json={
            "name": "Mallory",
            "email": "mallory@example.com",
            "phone": "416-555-0199",
            "password": "correct horse battery",
            "role": "Treasurer",
        },
    )

    assert response.status_code == 200
    profile = db_session.query(Profile).filter_by(email="mallory@example.com").one()
    assert profile.role is Role.customer


@scenario("A confirmation link works only once")
def test_confirmation_link_works_only_once(client, db_session):
    _sign_up(client)
    token = _confirmation_token(db_session, "cara@example.com")
    client.post("/api/profiles/confirm", json={"token": token})

    response = client.post("/api/profiles/confirm", json={"token": token})

    assert response.status_code == 422
    assert response.json()["detail"] == "This link has already been used or has expired"
    profile = db_session.query(Profile).filter_by(email="cara@example.com").one()
    assert profile.confirmed_at is not None


@scenario("An unconfirmed profile is deleted after 4 days")
def test_unconfirmed_profile_is_swept_after_four_days(client, db_session, clock: FakeClock):
    _sign_up(client)

    clock.advance(timedelta(days=4, minutes=1))
    sweep_pending_profiles(db_session, clock=clock)

    assert db_session.query(Profile).filter_by(email="cara@example.com").first() is None


@scenario("A confirmation link followed after 4 days is refused")
def test_confirmation_link_after_four_days_is_refused(client, db_session, clock: FakeClock):
    _sign_up(client)
    token = _confirmation_token(db_session, "cara@example.com")

    clock.advance(timedelta(days=4, minutes=1))
    response = client.post("/api/profiles/confirm", json={"token": token})

    assert response.status_code == 422
    assert response.json()["detail"] == "This link has already been used or has expired"
    profile = db_session.query(Profile).filter_by(email="cara@example.com").one()
    assert profile.confirmed_at is None


@scenario("Signing up with a member's email address leaves their profile unchanged")
def test_sign_up_with_a_confirmed_members_email_changes_nothing(client, db_session, clock):
    _sign_up(client)
    token = _confirmation_token(db_session, "cara@example.com")
    client.post("/api/profiles/confirm", json={"token": token})
    original = db_session.query(Profile).filter_by(email="cara@example.com").one()
    original_hash = original.password_hash

    response = _sign_up(client, email="CARA@example.com", password="a different passphrase")

    assert response.status_code == 200
    assert response.json()["message"] == "Check your email for a confirmation link"
    profile = db_session.query(Profile).filter_by(email="cara@example.com").one()
    assert profile.password_hash == original_hash
    assert db_session.query(Outbox).filter_by(to="cara@example.com").count() == 1


@scenario("Signing up again with a pending email address changes nothing")
def test_sign_up_again_with_a_pending_email_changes_nothing(client, db_session):
    _sign_up(client)
    pending = db_session.query(Profile).filter_by(email="cara@example.com").one()
    original_hash = pending.password_hash
    original_token = db_session.query(ConfirmationToken).filter_by(profile_id=pending.id).one()

    response = _sign_up(client, email="cara@example.com", password="a different passphrase")

    assert response.status_code == 200
    profile = db_session.query(Profile).filter_by(email="cara@example.com").one()
    assert profile.password_hash == original_hash
    token = db_session.query(ConfirmationToken).filter_by(profile_id=pending.id).one()
    assert token.token_hash == original_token.token_hash


@scenario("Two sign-ups with one email address at once create one profile")
def test_concurrent_sign_ups_create_one_profile(client_factory, db_session):
    first = client_factory()
    second = client_factory()

    response_one = _sign_up(first)
    response_two = _sign_up(second)

    assert response_one.status_code == 200
    assert response_two.status_code == 200
    assert db_session.query(Profile).filter_by(email="cara@example.com").count() == 1


@scenario("Wrong coach codes from one client address are throttled")
def test_wrong_coach_codes_from_one_address_are_throttled(client_factory, db_session):
    attacker = client_factory("203.0.113.5")
    for i in range(10):
        _sign_up(attacker, email=f"wrong{i}@example.com", coach_code="WRONG-CODE")

    response = _sign_up(attacker, email="colm@example.com", coach_code=COACH_CODE)

    assert response.status_code == 429
    assert response.json()["detail"] == "Too many attempts. Try again later"
    assert db_session.query(Profile).filter_by(email="colm@example.com").first() is None
