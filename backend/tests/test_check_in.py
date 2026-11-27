import threading
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.check_ins import AlreadyCheckedInError, check_in
from app.cli import create_treasurer
from app.db import Base
from app.models import CheckIn, ClassSession, Profile, Role
from app.security import hash_password

from .conftest import FakeClock, scenario

CLUB_TIMEZONE = ZoneInfo("America/Toronto")


def local(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    """A club-local time (America/Toronto), as the UTC instant the clock reports."""
    return datetime(year, month, day, hour, minute, tzinfo=CLUB_TIMEZONE).astimezone(UTC)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(local(2026, 12, 3, 18, 5))


def _make_coach(db_session: Session, *, email: str, name: str) -> Profile:
    profile = Profile(
        name=name,
        email=email.lower(),
        phone=None,
        password_hash=hash_password("coach passphrase"),
        role=Role.coach,
        confirmed_at=local(2026, 12, 1, 9, 0),
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
        confirmed_at=local(2026, 12, 1, 9, 0),
    )
    db_session.add(profile)
    db_session.commit()
    return profile


def _sign_in(client, email: str, password: str) -> None:
    response = client.post("/api/auth/sign-in", json={"email": email, "password": password})
    assert response.status_code == 200


def _seed_attended(db_session: Session, *, profile: Profile, count: int, created_by: int) -> None:
    """Give `profile` `count` past checked-in sessions, each distinct."""
    for i in range(count):
        session = ClassSession(
            start=datetime(2026, 11, 1 + i, 10, 0, tzinfo=UTC),
            length_minutes=60,
            price_cents=1000,
            created_by=created_by,
        )
        db_session.add(session)
        db_session.flush()
        db_session.add(
            CheckIn(
                profile_id=profile.id,
                session_id=session.id,
                checked_in_at=session.start,
                price_cents=1000,
                paid_at=None,
            )
        )
    db_session.commit()


@pytest.fixture
def colm(db_session: Session) -> Profile:
    return _make_coach(db_session, email="colm@example.com", name="Colm")


@pytest.fixture
def cara(db_session: Session) -> Profile:
    return _make_customer(db_session, email="cara@example.com", name="Cara")


@pytest.fixture
def session_in_progress(db_session: Session, colm: Profile) -> ClassSession:
    session = ClassSession(
        start=local(2026, 12, 3, 18, 0),
        length_minutes=60,
        price_cents=1500,
        created_by=colm.id,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@scenario("A Customer checks in to the session in progress")
def test_customer_checks_in_to_session_in_progress(
    client, db_session, clock, cara, session_in_progress
):
    _seed_attended(db_session, profile=cara, count=4, created_by=session_in_progress.created_by)
    _sign_in(client, "cara@example.com", "customer passphrase")

    response = client.post("/api/check-ins")

    assert response.status_code == 201
    body = response.json()
    assert body["price"] == 15.00
    assert body["sessions_attended"] == 5
    record = (
        db_session.query(CheckIn)
        .filter_by(profile_id=cara.id, session_id=session_in_progress.id)
        .one()
    )
    assert record.price_cents == 1500
    assert record.paid_at is None


@scenario("Check-in opens 15 minutes before the start")
def test_check_in_opens_15_minutes_before_the_start(
    client, db_session, clock, cara, session_in_progress
):
    clock._now = local(2026, 12, 3, 17, 45)
    _sign_in(client, "cara@example.com", "customer passphrase")

    response = client.post("/api/check-ins")

    assert response.status_code == 201
    assert db_session.query(CheckIn).filter_by(profile_id=cara.id).count() == 1


@pytest.mark.parametrize(
    ("year", "month", "day", "hour", "minute"),
    [
        (2026, 12, 3, 17, 44),
        (2026, 12, 3, 19, 0),
        (2026, 12, 4, 18, 5),
    ],
)
@scenario("Check-in with no session in progress is refused")
def test_check_in_with_no_session_in_progress_is_refused(
    client, db_session, clock, cara, session_in_progress, year, month, day, hour, minute
):
    clock._now = local(year, month, day, hour, minute)
    _sign_in(client, "cara@example.com", "customer passphrase")

    response = client.post("/api/check-ins")

    assert response.status_code == 404
    assert response.json()["detail"] == "There is no session to check in to right now"
    assert db_session.query(CheckIn).count() == 0


@scenario("A Coach checks in and owes nothing")
def test_coach_checks_in_and_owes_nothing(client, db_session, clock, colm, session_in_progress):
    clock._now = local(2026, 12, 3, 17, 50)
    _sign_in(client, "colm@example.com", "coach passphrase")

    response = client.post("/api/check-ins")

    assert response.status_code == 201
    assert response.json()["price"] == 0.0
    record = db_session.query(CheckIn).filter_by(profile_id=colm.id).one()
    assert record.price_cents == 0


@scenario("Checking in twice to one session is refused")
def test_checking_in_twice_to_one_session_is_refused(
    client, db_session, clock, cara, session_in_progress
):
    _sign_in(client, "cara@example.com", "customer passphrase")
    first = client.post("/api/check-ins")
    assert first.status_code == 201

    response = client.post("/api/check-ins")

    assert response.status_code == 409
    assert response.json()["detail"] == "You have already checked in to this session"
    assert db_session.query(CheckIn).filter_by(profile_id=cara.id).count() == 1


@scenario("Two check-ins by one member at once record one")
def test_two_check_ins_by_one_member_at_once_record_one(tmp_path, clock):
    """A dedicated file-backed engine, so the two check-ins run on genuinely
    independent connections and SQLite's own locking decides the race. The
    shared in-memory engine the other tests use has one connection behind
    it and cannot exercise that.
    """
    engine = create_engine(
        f"sqlite:///{tmp_path / 'race.sqlite3'}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    setup = session_factory()
    cara = _make_customer(setup, email="cara@example.com", name="Cara")
    colm = _make_coach(setup, email="colm@example.com", name="Colm")
    session = ClassSession(
        start=local(2026, 12, 3, 18, 0), length_minutes=60, price_cents=1500, created_by=colm.id
    )
    setup.add(session)
    setup.commit()
    cara_id, session_id = cara.id, session.id
    setup.close()

    outcomes: list[bool] = []

    def attempt() -> None:
        db = session_factory()
        try:
            profile = db.get(Profile, cara_id)
            check_in(db, profile=profile, clock=clock)
            outcomes.append(True)
        except AlreadyCheckedInError:
            outcomes.append(False)
        finally:
            db.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    engine.dispose()

    assert sorted(outcomes) == [False, True]
    verify = session_factory()
    assert verify.query(CheckIn).filter_by(profile_id=cara_id, session_id=session_id).count() == 1
    verify.close()


@scenario("A check-in is for the signed-in member, whatever the request names")
def test_check_in_is_for_signed_in_member_whatever_the_request_names(
    client, db_session, clock, cara, colm, session_in_progress
):
    _sign_in(client, "cara@example.com", "customer passphrase")

    response = client.post("/api/check-ins", json={"member": "colm@example.com"})

    assert response.status_code == 201
    assert db_session.query(CheckIn).filter_by(profile_id=cara.id).count() == 1
    assert db_session.query(CheckIn).filter_by(profile_id=colm.id).count() == 0


@scenario("The Treasurer cannot check in")
def test_treasurer_cannot_check_in(client, db_session, clock, session_in_progress):
    create_treasurer(
        db_session, "Tess Okafor", "tess@example.com", "treasurer passphrase", clock.now()
    )
    _sign_in(client, "tess@example.com", "treasurer passphrase")

    response = client.post("/api/check-ins")

    assert response.status_code == 403
    assert db_session.query(CheckIn).count() == 0
