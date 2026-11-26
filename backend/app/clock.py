"""Time as an injected dependency, so tests can control it."""

from datetime import UTC, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

CLUB_TIMEZONE = ZoneInfo("America/Toronto")


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def get_clock() -> Clock:
    return SystemClock()
