"""Friendly dates for the screens: "Today, 10:51 AM", "Yesterday", "Sep 28"."""

from datetime import datetime


def _parse(stamp: str | None) -> datetime | None:
    return datetime.fromisoformat(stamp) if stamp else None


def clock(t: datetime) -> str:
    return f"{t.hour % 12 or 12}:{t:%M %p}"


def day(stamp: str | None) -> str:
    t = _parse(stamp)
    return f"{t:%b} {t.day}" if t else ""


def full(stamp: str | None) -> str:
    """'Oct 1, 11:05 AM'"""
    t = _parse(stamp)
    return f"{t:%b} {t.day}, {clock(t)}" if t else ""


def friendly(stamp: str | None, now: datetime | None = None) -> str:
    t = _parse(stamp)
    if not t:
        return ""
    now = now or datetime.now()
    days = (now.date() - t.date()).days
    if days == 0:
        return f"Today, {clock(t)}"
    if days == 1:
        return "Yesterday"
    return f"{t:%b} {t.day}" if t.year == now.year else f"{t:%b} {t.day}, {t.year}"
