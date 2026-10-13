"""Pure constraint helpers for Proposal/PP/Viva academic scheduling."""

from __future__ import annotations

from datetime import datetime


PANEL_REQUIREMENTS = (("prof_dr", 2), ("lecturer", 1), ("instructor", 1))


def academic_role_key(role: str) -> str:
    value = (role or "").strip().lower()
    if "instructor" in value:
        return "instructor"
    if "lecturer" in value:
        return "lecturer"
    if any(word in value for word in ("prof", "doctor", "dr")):
        return "prof_dr"
    return "other"


def academic_role_label(role: str) -> str:
    return {
        "prof_dr": "Professor / Doctor",
        "lecturer": "Lecturer",
        "instructor": "Instructor",
    }.get(academic_role_key(role), role or "Academic Staff")


def minutes(time_value: str) -> int:
    parsed = datetime.strptime(time_value.strip(), "%H:%M")
    return parsed.hour * 60 + parsed.minute


def clock(total_minutes: int) -> str:
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def interval_free(bookings: list[tuple[int, int]], start: int, end: int) -> bool:
    return all(end <= used_start or start >= used_end for used_start, used_end in bookings)


def select_academic_panel(scored_supervisors: list[tuple[float, tuple]]) -> list[tuple[float, tuple]]:
    """Select exactly two Prof/Dr, one Lecturer and one Instructor."""
    selected = []
    selected_ids = set()
    for role, required in PANEL_REQUIREMENTS:
        candidates = [
            item for item in scored_supervisors
            if academic_role_key(item[1][5]) == role and item[1][0] not in selected_ids
        ]
        if len(candidates) < required:
            raise ValueError(f"Insufficient academic staff for required role: {role}")
        for item in candidates[:required]:
            selected.append(item)
            selected_ids.add(item[1][0])
    return selected
