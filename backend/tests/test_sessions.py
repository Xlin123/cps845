from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models import ClassSession, NoticeKind, Profile, Role, SessionDeletion, SessionNotice
from app.security import hash_password

from .conftest import FakeClock, scenario

# The feature's Background fixes the time at 2026-12-01 09:00 club-local
# (America/Toronto, UTC-5 in December), i.e. 2026-12-01 14:00 UTC.
NOW_UTC = datetime(2026, 12, 1, 14, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW_UTC)


def _make_coach(db_session: Session, *, email: str, name: str) -> Profile:
    profile = Profile(
        name=name,
        email=email.lower(),
        phone=None,
        password_hash=hash_password("coach passphrase"),
        role=Role.coach,
        confirmed_at=NOW_UTC,
    )
    db_session.add(profile)
    db_session.commit()
    return profile


def _make_customer(db_session: Session, *, email: str, name: str) -> Profile:
    profile = Profile(
        name=name,
        email=email.lower(),
        phone=None,
        password_hash=hash_password("customer passphrase"),
        role=Role.customer,
        confirmed_at=NOW_UTC,
    )
    db_session.add(profile)
    db_session.commit()
    return profile


def _sign_in(client, email: str, password: str) -> None:
    response = client.post("/api/auth/sign-in", json={"email": email, "password": password})
    assert response.status_code == 200


@pytest.fixture
def colm(db_session: Session) -> Profile:
    return _make_coach(db_session, email="colm@example.com", name="Colm")


@pytest.fixture
def cora(db_session: Session) -> Profile:
    return _make_coach(db_session, email="cora@example.com", name="Cora")


@pytest.fixture
def cara(db_session: Session) -> Profile:
    return _make_customer(db_session, email="cara@example.com", name="Cara")


def _create(
    client,
    *,
    date="2026-12-03",
    start_time="18:00",
    length_minutes=60,
    price=15.00,
    overwrite_ids=None,
):
    body = {
        "date": date,
        "start_time": start_time,
        "length_minutes": length_minutes,
        "price": price,
    }
    if overwrite_ids is not None:
        body["overwrite_ids"] = overwrite_ids
    return client.post("/api/sessions", json=body)


@scenario("A Coach creates a session and a session-created notice is queued")
def test_coach_creates_session_and_notice_is_queued(client, db_session, clock, colm):
    _sign_in(client, "colm@example.com", "coach passphrase")

    response = _create(client)

    assert response.status_code == 201
    session = db_session.query(ClassSession).one()
    assert session.length_minutes == 60
    assert session.price_cents == 1500
    assert session.created_by == colm.id
    notice = db_session.query(SessionNotice).one()
    assert notice.kind == NoticeKind.created
    assert notice.session_id == session.id


@scenario("An overlapping session asks the Coach to overwrite or cancel")
def test_overlapping_session_asks_to_overwrite_or_cancel(client, db_session, clock, colm):
    _sign_in(client, "colm@example.com", "coach passphrase")
    _create(client)

    response = _create(client, start_time="18:30")

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["can_overwrite"] is True
    assert "2026-12-03 18:00" in detail["detail"]


@scenario("Overwriting replaces the colliding session")
def test_overwriting_replaces_the_colliding_session(client, db_session, clock, colm):
    _sign_in(client, "colm@example.com", "coach passphrase")
    _create(client)
    original_id = db_session.query(ClassSession).one().id

    asked = _create(client, start_time="18:30", price=20.00)
    response = _create(client, start_time="18:30", price=20.00, overwrite_ids=[original_id])

    assert asked.status_code == 409
    assert response.status_code == 201
    assert db_session.query(ClassSession).filter_by(id=original_id).first() is None
    new_session = db_session.query(ClassSession).one()
    assert new_session.price_cents == 2000
    deletion = db_session.query(SessionDeletion).one()
    assert deletion.deleted_by == colm.id


@scenario("Cancelling at the collision prompt changes nothing")
def test_cancelling_at_collision_prompt_changes_nothing(client, db_session, clock, colm):
    _sign_in(client, "colm@example.com", "coach passphrase")
    _create(client)

    _create(client, start_time="18:30")

    assert db_session.query(ClassSession).count() == 1
    assert db_session.query(SessionNotice).filter_by(kind=NoticeKind.created).count() == 1


@scenario("Sessions that only touch do not collide")
def test_sessions_that_only_touch_do_not_collide(client, db_session, clock, colm):
    _sign_in(client, "colm@example.com", "coach passphrase")
    _create(client)

    response = _create(client, start_time="19:00")

    assert response.status_code == 201
    assert db_session.query(ClassSession).count() == 2


@scenario("A collision with a session in progress can only be cancelled")
def test_collision_with_session_in_progress_can_only_be_cancelled(client, db_session, clock, colm):
    # The in-progress session already exists before "now" (it started at
    # 08:30, before the Background's 09:00); seed it directly, since Create
    # Session itself refuses any start that isn't in the future.
    db_session.add(
        ClassSession(
            start=datetime(2026, 12, 1, 13, 30, tzinfo=UTC),
            length_minutes=90,
            price_cents=1500,
            created_by=colm.id,
        )
    )
    db_session.commit()
    _sign_in(client, "colm@example.com", "coach passphrase")

    response = _create(client, date="2026-12-01", start_time="09:30")

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["can_overwrite"] is False
    assert "in progress" in detail["detail"]


@scenario("A Coach can overwrite another Coach's session")
def test_coach_can_overwrite_another_coachs_session(client, db_session, clock, colm, cora):
    _sign_in(client, "cora@example.com", "coach passphrase")
    _create(client)
    cora_session_id = db_session.query(ClassSession).one().id

    client.post("/api/auth/sign-out")
    _sign_in(client, "colm@example.com", "coach passphrase")
    response = _create(client, length_minutes=90, overwrite_ids=[cora_session_id])

    assert response.status_code == 201
    assert db_session.query(ClassSession).filter_by(id=cora_session_id).first() is None
    deletion = db_session.query(SessionDeletion).one()
    assert deletion.created_by == cora.id
    assert deletion.deleted_by == colm.id


@pytest.mark.parametrize(
    ("date", "start_time", "length_minutes", "price", "error"),
    [
        ("2026-12-01", "08:00", 60, 15.00, "A session must start in the future"),
        ("2027-12-02", "18:00", 60, 15.00, "A session must start within 365 days"),
        ("2026-12-03", "18:00", 14, 15.00, "A session lasts 15 to 480 minutes"),
        ("2026-12-03", "18:00", 481, 15.00, "A session lasts 15 to 480 minutes"),
        ("2026-12-03", "18:00", 60, -1.00, "A price is 0.00 to 1,000.00"),
        ("2026-12-03", "18:00", 60, 1000.01, "A price is 0.00 to 1,000.00"),
        ("2026-12-03", "18:00", 60, 15.005, "A price is 0.00 to 1,000.00"),
    ],
)
@scenario("A session outside the bounds is refused")
def test_session_outside_bounds_is_refused(
    client, db_session, clock, colm, date, start_time, length_minutes, price, error
):
    _sign_in(client, "colm@example.com", "coach passphrase")

    response = _create(
        client, date=date, start_time=start_time, length_minutes=length_minutes, price=price
    )

    assert response.status_code == 400
    assert response.json()["detail"] == error
    assert db_session.query(ClassSession).count() == 0


@scenario("An overwrite is asked again when the colliding sessions have changed")
def test_overwrite_is_asked_again_when_colliding_sessions_changed(
    client, db_session, clock, colm, cora
):
    _sign_in(client, "colm@example.com", "coach passphrase")
    _create(client)
    first_id = db_session.query(ClassSession).one().id

    asked = _create(client, start_time="18:30", length_minutes=90)
    assert asked.status_code == 409

    client.post("/api/auth/sign-out")
    _sign_in(client, "cora@example.com", "coach passphrase")
    _create(client, start_time="19:30", length_minutes=30)

    client.post("/api/auth/sign-out")
    _sign_in(client, "colm@example.com", "coach passphrase")
    response = _create(client, start_time="18:30", length_minutes=90, overwrite_ids=[first_id])

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["can_overwrite"] is True
    assert len(detail["collisions"]) == 2
    assert db_session.query(ClassSession).count() == 2


@scenario("A create request sent again does not make a duplicate")
def test_create_request_sent_again_does_not_make_duplicate(client, db_session, clock, colm):
    _sign_in(client, "colm@example.com", "coach passphrase")
    _create(client)

    response = _create(client)

    assert response.status_code == 409
    assert db_session.query(ClassSession).count() == 1


@scenario("A Customer cannot create a session")
def test_customer_cannot_create_a_session(client, db_session, clock, cara):
    _sign_in(client, "cara@example.com", "customer passphrase")

    response = _create(client)

    assert response.status_code == 403
    assert db_session.query(ClassSession).count() == 0


@scenario("A session records the signed-in Coach, whatever the request names")
def test_session_records_signed_in_coach_whatever_request_names(
    client, db_session, clock, colm, cora
):
    _sign_in(client, "colm@example.com", "coach passphrase")

    body = {
        "date": "2026-12-03",
        "start_time": "18:00",
        "length_minutes": 60,
        "price": 15.00,
        "created_by": cora.id,
    }
    response = client.post("/api/sessions", json=body)

    assert response.status_code == 201
    session = db_session.query(ClassSession).one()
    assert session.created_by == colm.id
