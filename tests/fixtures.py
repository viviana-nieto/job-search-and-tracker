"""Shared test fixtures for deterministic time-dependent tests."""
from datetime import date, datetime, timezone


class FixedClock:
    """Deterministic clock. Use it by passing its .today() or .now() result
    (or directly via the `today` / `now` kwargs) to tracking functions.

    Example:
        clock = FixedClock("2026-04-11")
        tracking.save(data, today=clock.today_str())
    """

    def __init__(self, iso_date: str = "2026-04-11", iso_datetime: str = None):
        self._today = date.fromisoformat(iso_date)
        if iso_datetime:
            self._now = datetime.fromisoformat(iso_datetime)
        else:
            self._now = datetime(
                self._today.year,
                self._today.month,
                self._today.day,
                12,
                0,
                0,
                tzinfo=timezone.utc,
            )

    def today(self) -> date:
        return self._today

    def today_str(self) -> str:
        return self._today.isoformat()

    def now(self) -> datetime:
        return self._now

    def advance_days(self, n: int) -> "FixedClock":
        """Return a NEW FixedClock advanced by n days (immutable)."""
        new_date = date.fromordinal(self._today.toordinal() + n)
        return FixedClock(new_date.isoformat())
