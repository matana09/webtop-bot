"""Manual timetable — the printed class sheet, applied on top of API data.

Webtop blocks the schedule view between school years ("view is blocked"), and
in the first weeks of a new year the API data is often missing or wrong, so a
printed sheet entered here can act as the source of truth.

A day listed below is *fully* specified: an hour the API returns for that day
but that is missing here is dropped. That way the sheet still wins once the
API comes back.

Format: {day_idx: {hour_num: (subject, teacher)}} — an optional third element
adds the current unit topic, e.g. ("מתמטיקה", "", "כפל וחילוק").
day_idx: 1=ראשון, 2=שני, 3=שלישי, 4=רביעי, 5=חמישי, 6=שישי
"""

OVERRIDES: dict[int, dict[int, tuple[str, ...]]] = {
    # Example — fill in only if the API returns a wrong/blank day for you:
    # 2: {                                    # Monday
    #     1: ("מתמטיקה", "", "כפל וחילוק"),   # (subject, teacher, topic)
    #     2: ("עברית", ""),                   # (subject, teacher)
    # },
}


def normalize(cell: tuple[str, ...]) -> tuple[str, str, str]:
    """Pad a (subject, teacher[, topic]) entry to a fixed 3-tuple.

    OVERRIDES is edited by hand, so the two easy slips are checked here: a
    bare string would otherwise unpack into its own characters, and a
    1-tuple would raise somewhere far away from the table you mistyped.
    """
    if isinstance(cell, str) or not 2 <= len(cell) <= 3:
        raise ValueError(
            f"OVERRIDES entry must be (subject, teacher) or "
            f"(subject, teacher, topic); got {cell!r}"
        )
    subject, teacher, *rest = cell
    return subject, teacher, (rest[0] if rest else "")


def for_day(day_idx: int) -> dict[int, tuple[str, str, str]] | None:
    """The full manual day, or None when the day is not overridden."""
    day = OVERRIDES.get(day_idx)
    return {hour: normalize(cell) for hour, cell in day.items()} if day else None


def apply(matrix: dict, day_indices: set) -> None:
    """Apply overrides in-place to the matrix built from API data.

    matrix: hour_num -> day_idx -> (subject, teacher, topic)
    """
    for day_idx, hours in OVERRIDES.items():
        day_indices.add(day_idx)
        # Drop API hours this day does not have any more
        for hour_num, by_day in matrix.items():
            if hour_num not in hours:
                by_day.pop(day_idx, None)
        for hour_num, cell in hours.items():
            matrix.setdefault(hour_num, {})[day_idx] = normalize(cell)

    # An hour left with no day at all would draw as a blank row
    for hour_num in [h for h, by_day in matrix.items() if not by_day]:
        del matrix[hour_num]
