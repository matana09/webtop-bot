"""
Manual schedule overrides — applied on top of API data.
Format: {day_idx: {hour_num: (subject, teacher)}}
day_idx: 1=ראשון, 2=שני, 3=שלישי, 4=רביעי, 5=חמישי, 6=שישי
"""

OVERRIDES: dict[int, dict[int, tuple[str, str]]] = {
    # Example — fill in only if the API returns a wrong/blank day for you:
    # 2: {                          # Monday
    #     1: ("מתמטיקה", ""),   # hour 1 -> (subject, teacher)
    #     2: ("עברית", ""),
    # },
}


def apply(matrix: dict, day_indices: set) -> None:
    """Apply overrides in-place to the matrix built from API data."""
    for day_idx, hours in OVERRIDES.items():
        day_indices.add(day_idx)
        for hour_num, cell in hours.items():
            matrix.setdefault(hour_num, {})[day_idx] = cell
