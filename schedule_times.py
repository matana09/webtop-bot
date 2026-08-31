"""School bell times — the single source for the text screens and the PNG.

Every school rings a different bell, so treat the tables below as defaults and
edit them to match yours. They used to live twice, in handlers/start.py and in
schedule_image.py, which is how the two drifted apart.
"""

# hour_num → (start, end)
HOUR_TIMES: dict[int, tuple[str, str]] = {
    1: ("8:00",  "8:40"),
    2: ("8:40",  "9:25"),
    3: ("10:05", "10:55"),
    4: ("10:55", "11:50"),
    5: ("12:00", "12:45"),
    6: ("12:45", "13:30"),
}

# Breaks inserted AFTER a given hour: after_hour → [(start, end, label)]
BREAKS_AFTER: dict[int, list[tuple[str, str, str]]] = {
    2: [
        ("9:25",  "9:45",  "🍽️ הפסקת אוכל"),
        ("9:45",  "10:05", "🏃 הפסקה"),
    ],
    4: [
        ("11:50", "12:00", "🏃 הפסקה"),
    ],
}

FRIDAY_IDX = 6

# Friday is a short day in Israeli schools: the last lesson ends early and no
# break follows it. Set to "" if your school runs Friday like any other day.
FRIDAY_LAST_HOUR = 4
FRIDAY_ENDS_AT = "11:40"


def hour_times_for_day(day_idx: int) -> dict[int, tuple[str, str]]:
    """Bell times for a given day — also the hook for per-day exceptions."""
    times = dict(HOUR_TIMES)
    if day_idx == FRIDAY_IDX and FRIDAY_ENDS_AT and FRIDAY_LAST_HOUR in times:
        times[FRIDAY_LAST_HOUR] = (times[FRIDAY_LAST_HOUR][0], FRIDAY_ENDS_AT)
    return times


def breaks_after_for_day(day_idx: int, hour_num: int) -> list[tuple[str, str, str]]:
    """Breaks after hour_num — nothing follows Friday's last lesson.

    Gated on FRIDAY_ENDS_AT like hour_times_for_day is, so clearing it turns
    off the whole Friday exception rather than half of it.
    """
    if day_idx == FRIDAY_IDX and hour_num == FRIDAY_LAST_HOUR and FRIDAY_ENDS_AT:
        return []
    return BREAKS_AFTER.get(hour_num, [])
