"""School vacations and holidays — the days that have no lessons.

Webtop has no vacation feed. On a day off it just returns an empty schedule,
which is indistinguishable from a day the API failed to load, so the bot used
to show a blank day and leave you guessing which of the two had happened.
The calendar therefore lives here, entered by hand.

Israel's Ministry of Education publishes the dates each summer, and every
school then adds its own days off on top, so no built-in table would be right
for anyone. The list below ships empty on purpose — fill in yours from the
calendar your school published, the same way schedule_overrides is filled in
from the printed timetable.

Both ends of a range are inclusive. A single day off is a range that starts
and ends on the same date.
"""
from datetime import date, datetime, timedelta

from schedule_times import israeli_day_index

# (start, end, label) — inclusive. Uncomment and edit; the dates below are
# placeholders showing the shape, NOT a real school calendar.
VACATIONS: list[tuple[date, date, str]] = [
    # (date(2026, 9, 21), date(2026, 9, 22), "ראש השנה"),
    # (date(2026, 9, 30), date(2026, 9, 30), "יום כיפור"),
    # (date(2026, 10, 5), date(2026, 10, 13), "חופשת סוכות"),
    # (date(2026, 12, 6), date(2026, 12, 13), "חופשת חנוכה"),
    # (date(2027, 3, 22), date(2027, 3, 23), "פורים"),
    # (date(2027, 4, 18), date(2027, 4, 28), "חופשת פסח"),
    # (date(2027, 6, 30), date(2027, 8, 31), "חופש הגדול"),
]

# Israeli day indices that are never school days. 7 = שבת.
# Some schools do not teach on Friday either — add 6 here if yours is one.
WEEKLY_REST_DAYS: set[int] = {7}

_REST_DAY_LABELS = {6: "יום שישי", 7: "שבת"}


def _normalize(entry: tuple) -> tuple[date, date, str]:
    """Validate one VACATIONS row.

    The table is edited by hand, so the slips worth catching are caught here
    rather than surfacing days later as a vacation that silently never fires:
    a reversed range, a string where a date was meant, a missing label.
    """
    if isinstance(entry, str) or len(entry) != 3:
        raise ValueError(
            f"VACATIONS entry must be (start_date, end_date, label); got {entry!r}"
        )
    start, end, label = entry
    if not isinstance(start, date) or not isinstance(end, date):
        raise ValueError(
            f"VACATIONS dates must be datetime.date objects, "
            f"e.g. date(2026, 4, 1); got {entry!r}"
        )
    # datetime is a subclass of date, and mixing the two raises TypeError on
    # the comparisons below. Narrow it here rather than at every comparison.
    start = start.date() if isinstance(start, datetime) else start
    end   = end.date()   if isinstance(end, datetime)   else end
    if end < start:
        raise ValueError(
            f"VACATIONS range ends before it starts: {start} → {end} ({label!r})"
        )
    if not str(label).strip():
        raise ValueError(f"VACATIONS entry needs a label; got {entry!r}")
    return start, end, str(label).strip()


def all_ranges() -> list[tuple[date, date, str]]:
    """Every configured range, validated and sorted by start date."""
    return sorted((_normalize(e) for e in VACATIONS), key=lambda r: r[0])


def vacation_for(day: date) -> str | None:
    """The vacation label covering this date, or None if it is not one."""
    for start, end, label in all_ranges():
        if start <= day <= end:
            return label
    return None


def rest_day_for(day: date) -> str | None:
    """The weekly-rest label for this date, or None if it is a teaching day."""
    idx = israeli_day_index(day)
    if idx in WEEKLY_REST_DAYS:
        return _REST_DAY_LABELS.get(idx, "יום מנוחה")
    return None


def off_reason(day: date) -> str | None:
    """Why there is no school on this date, or None when there is.

    A vacation wins over the weekly rest day, so a holiday that falls on a
    Shabbat still reports the holiday.
    """
    return vacation_for(day) or rest_day_for(day)


def is_school_day(day: date) -> bool:
    return off_reason(day) is None


def week_off_days(sunday: date) -> dict[int, str]:
    """day_idx → reason, for the Sun–Fri week beginning on `sunday`.

    Used to strike the vacation days through the weekly schedule image.
    """
    off: dict[int, str] = {}
    for offset in range(6):                    # Sunday…Friday
        day = sunday + timedelta(days=offset)
        reason = off_reason(day)
        if reason:
            off[israeli_day_index(day)] = reason
    return off


def next_school_day(day: date, limit: int = 400) -> date | None:
    """The first teaching day strictly after `day`.

    Bounded so that a mistyped range — an end date years past its start —
    cannot spin here forever; it returns None instead.
    """
    probe = day
    for _ in range(limit):
        probe += timedelta(days=1)
        if is_school_day(probe):
            return probe
    return None


def upcoming(today: date | None = None, limit: int = 5) -> list[tuple[date, date, str]]:
    """The next few vacations that have not finished yet, soonest first."""
    today = today or date.today()
    return [r for r in all_ranges() if r[1] >= today][:limit]


def describe(start: date, end: date, label: str) -> str:
    """One human line for a range: the label, its dates, and its length."""
    days = (end - start).days + 1
    when = (start.strftime("%d/%m/%Y") if start == end
            else f"{start.strftime('%d/%m/%Y')} – {end.strftime('%d/%m/%Y')}")
    return f"{label} — {when} ({days} ימים)" if days > 1 else f"{label} — {when}"
