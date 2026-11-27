from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models import ClassSession, NoticeKind, Profile, Role, SessionDeletion, SessionNotice
from app.security import hash_password

from .conftest import FakeClock, scenario

# The feature's Background fixes the time at 2026-12-01 09:00 club-local
# (America/Toronto, UTC-5 in December), i.e. 2026-12-01 14:00 UTC.
NOW_UTC = datetime(2026, 12, 1, 14, 0, tzinfo=UTC)
SESSION_1203_UTC = datetime(2026, 12, 3, 23, 0, tzinfo=UTC)  # 18:00 club-local
SESSION_1205_UTC = datetime(2026, 12, 5, 23, 0, tzinfo=UTC)  # 18:00 club-local


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


def _seed_session(
    db_session: Session, *, start: datetime, created_by: int, length_minutes: int = 60
) -> ClassSession:
    session = ClassSession(
        start=start, length_minutes=length_minutes, price_cents=1500, created_by=created_by
    )
    db_session.add(session)
    db_session.commit()
    return session


def _queue_created_notice(db_session: Session, session: ClassSession) -> None:
    db_session.add(
        SessionNotice(
            kind=NoticeKind.created,
            session_id=session.id,
            start=session.start,
            length_minutes=session.length_minutes,
            price_cents=session.price_cents,
        )
    )
    db_session.commit()


def _delete(client, session_ids: list[int]):
    return client.request("DELETE", "/api/sessions", json={"session_ids": session_ids})


@scenario("Confirming deletes every selected session")
def test_confirming_deletes_every_selected_session(client, db_session, clock, colm):
    session_1203 = _seed_session(db_session, start=SESSION_1203_UTC, created_by=colm.id)
    session_1205 = _seed_session(db_session, start=SESSION_1205_UTC, created_by=colm.id)
    _sign_in(client, "colm@example.com", "coach passphrase")

    response = _delete(client, [session_1203.id, session_1205.id])

    assert response.status_code == 204
    assert db_session.query(ClassSession).count() == 0
    deletions = db_session.query(SessionDeletion).all()
    assert len(deletions) == 2
    assert all(d.deleted_by == colm.id for d in deletions)


@scenario("Deleting a session whose notice is unsent drops the notice")
def test_deleting_session_with_unsent_notice_drops_the_notice(client, db_session, clock, colm):
    session = _seed_session(db_session, start=SESSION_1203_UTC, created_by=colm.id)
    _queue_created_notice(db_session, session)
    _sign_in(client, "colm@example.com", "coach passphrase")

    response = _delete(client, [session.id])

    assert response.status_code == 204
    assert db_session.query(SessionNotice).count() == 0


@scenario("Deleting a session whose notice was sent queues a session-deleted notice")
def test_deleting_session_with_sent_notice_queues_deleted_notice(client, db_session, clock, colm):
    session = _seed_session(db_session, start=SESSION_1203_UTC, created_by=colm.id)
    _sign_in(client, "colm@example.com", "coach passphrase")

    response = _delete(client, [session.id])

    assert response.status_code == 204
    notice = db_session.query(SessionNotice).one()
    assert notice.kind == NoticeKind.deleted
    assert notice.session_id is None


@scenario("A Coach can delete another Coach's session")
def test_coach_can_delete_another_coachs_session(client, db_session, clock, colm, cora):
    session = _seed_session(db_session, start=SESSION_1205_UTC, created_by=cora.id)
    _sign_in(client, "colm@example.com", "coach passphrase")

    response = _delete(client, [session.id])

    assert response.status_code == 204
    deletion = db_session.query(SessionDeletion).one()
    assert deletion.created_by == cora.id
    assert deletion.deleted_by == colm.id


@scenario("A selected session that starts before the Yes stops the whole delete")
def test_session_starting_before_yes_stops_whole_delete(client, db_session, clock, colm):
    session_1203 = _seed_session(db_session, start=SESSION_1203_UTC, created_by=colm.id)
    session_1205 = _seed_session(db_session, start=SESSION_1205_UTC, created_by=colm.id)
    _sign_in(client, "colm@example.com", "coach passphrase")

    clock.advance(timedelta(days=3))  # now past 2026-12-03 18:00 club-local

    response = _delete(client, [session_1203.id, session_1205.id])

    assert response.status_code == 409
    assert db_session.query(ClassSession).count() == 2


@scenario("Two Coaches deleting one session at once delete it once")
def test_two_coaches_deleting_one_session_at_once_delete_it_once(
    client, client_factory, db_session, clock, colm, cora
):
    session = _seed_session(db_session, start=SESSION_1203_UTC, created_by=colm.id)
    colm_client = client
    cora_client = client_factory("other-client")
    _sign_in(colm_client, "colm@example.com", "coach passphrase")
    _sign_in(cora_client, "cora@example.com", "coach passphrase")

    first = _delete(colm_client, [session.id])
    second = _delete(cora_client, [session.id])

    assert first.status_code == 204
    assert second.status_code == 409
    assert db_session.query(ClassSession).count() == 0
    assert db_session.query(SessionDeletion).count() == 1


@scenario("A delete request sent again changes nothing")
def test_delete_request_sent_again_changes_nothing(client, db_session, clock, colm):
    session_1203 = _seed_session(db_session, start=SESSION_1203_UTC, created_by=colm.id)
    session_1205 = _seed_session(db_session, start=SESSION_1205_UTC, created_by=colm.id)
    _sign_in(client, "colm@example.com", "coach passphrase")

    first = _delete(client, [session_1203.id])
    second = _delete(client, [session_1203.id])

    assert first.status_code == 204
    assert second.status_code == 409
    assert db_session.query(ClassSession).filter_by(id=session_1205.id).first() is not None
    assert db_session.query(SessionDeletion).count() == 1


@scenario("A delete of more than 100 sessions is refused")
def test_delete_of_more_than_100_sessions_is_refused(client, db_session, clock, colm):
    session_ids = []
    for i in range(101):
        session = _seed_session(
            db_session, start=SESSION_1203_UTC + timedelta(minutes=i), created_by=colm.id
        )
        session_ids.append(session.id)
    _sign_in(client, "colm@example.com", "coach passphrase")

    response = _delete(client, session_ids)

    assert response.status_code == 400
    assert response.json()["detail"] == "Delete at most 100 sessions at a time"
    assert db_session.query(ClassSession).count() == 101


@scenario("A Customer cannot delete a session")
def test_customer_cannot_delete_a_session(client, db_session, clock, colm, cara):
    session = _seed_session(db_session, start=SESSION_1203_UTC, created_by=colm.id)
    _sign_in(client, "cara@example.com", "customer passphrase")

    response = _delete(client, [session.id])

    assert response.status_code == 403
    assert db_session.query(ClassSession).filter_by(id=session.id).first() is not None


@scenario("The deletion log names the signed-in Coach, whatever the request names")
def test_deletion_log_names_signed_in_coach(client, db_session, clock, colm, cora):
    session = _seed_session(db_session, start=SESSION_1203_UTC, created_by=colm.id)
    _sign_in(client, "colm@example.com", "coach passphrase")

    response = client.request(
        "DELETE",
        "/api/sessions",
        json={"session_ids": [session.id], "deleted_by": cora.id},
    )

    assert response.status_code == 204
    deletion = db_session.query(SessionDeletion).one()
    assert deletion.deleted_by == colm.id
