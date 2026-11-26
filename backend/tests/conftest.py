"""Shared fixtures for backend tests, and the @scenario marker.

@scenario binds a test to the Gherkin scenario it proves, by title.
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.clock import get_clock
from app.db import Base, get_db
from app.main import app


def scenario(title: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        return pytest.mark.scenario(title)(func)

    return decorator


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 12, 1, 9, 0, tzinfo=UTC))


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine) -> Iterator:
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client_factory(engine, clock: FakeClock) -> Iterator[Callable[[str], TestClient]]:
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Iterator:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def override_get_clock() -> FakeClock:
        return clock

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_clock] = override_get_clock

    created: list[TestClient] = []

    def make(address: str = "testclient") -> TestClient:
        test_client = TestClient(app, client=(address, 12345))
        created.append(test_client)
        return test_client

    yield make

    for test_client in created:
        test_client.close()
    app.dependency_overrides.clear()


@pytest.fixture
def client(client_factory: Callable[[str], TestClient]) -> TestClient:
    return client_factory()
