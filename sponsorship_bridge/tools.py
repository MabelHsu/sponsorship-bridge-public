"""
tools.py — Standalone Utility Tools
────────────────────────────────────
Tools that don't depend on MCP connections, YouTube, or scoring.
Used by sub-agents (e.g. scheduling_agent) for deterministic operations.
"""

import re
from datetime import datetime, timedelta, timezone


def resolve_relative_date(
    date_phrase: str,
    reference_date: str = "",
) -> dict:
    """Resolve relative scheduling phrases into an exact ISO date deterministically.

    Supported phrases:
      - today
      - tomorrow
      - this <weekday>    (Monday ... Sunday)
      - next <weekday>    (Monday ... Sunday, always in the following week)

    Args:
        date_phrase: Natural language date phrase from user text.
        reference_date: Optional YYYY-MM-DD override for deterministic testing.
                        If empty, uses current UTC date.
    """
    phrase = (date_phrase or "").strip().lower()
    if not phrase:
        return {"status": "error", "error": "date_phrase is required"}

    if reference_date:
        try:
            base_date = datetime.strptime(reference_date, "%Y-%m-%d").date()
        except ValueError:
            return {
                "status": "error",
                "error": "reference_date must be in YYYY-MM-DD format",
            }
    else:
        base_date = datetime.now(timezone.utc).date()

    if phrase == "today":
        resolved_date = base_date
    elif phrase == "tomorrow":
        resolved_date = base_date + timedelta(days=1)
    else:
        match = re.match(
            r"^(this|next)\s+"
            r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$",
            phrase,
        )
        if not match:
            return {
                "status": "error",
                "error": (
                    "Unsupported date phrase. Use today, tomorrow, this <weekday>, "
                    "or next <weekday>."
                ),
            }

        qualifier, weekday_name = match.groups()
        weekday_index = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
        }[weekday_name]

        current_weekday = base_date.weekday()
        delta = (weekday_index - current_weekday) % 7

        if qualifier == "this":
            resolved_date = base_date if delta == 0 else base_date + timedelta(days=delta)
        else:  # "next"
            if delta == 0:
                delta = 7
            resolved_date = base_date + timedelta(days=delta)

    return {
        "status": "ok",
        "input_phrase": date_phrase,
        "reference_date": base_date.isoformat(),
        "resolved_date": resolved_date.isoformat(),
        "resolved_weekday": resolved_date.strftime("%A"),
    }
