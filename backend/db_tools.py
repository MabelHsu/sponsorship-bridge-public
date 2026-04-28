"""
Database tools for Sponsorship Bridge.

Uses SQLite (built-in, zero dependencies) to store brand campaigns
and match results. The database file lives in the working directory.

Tools:
  - get_active_brand_campaigns: Read brand campaigns from DB (Creator Mode)
  - save_match_result:          Store a match after scoring (both modes)
  - get_match_history:          Retrieve past match results (reporting)

Setup: Run `python db_tools.py` once to create the database and seed data.
"""

import sqlite3
import os

# Use absolute path so the DB is always found regardless of which directory
# the agent or Docker container runs from (project root, /app, etc.)
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sponsorship.db")


def init_db():
    """Initialize the database and load schema.sql with mock data."""
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "infra", "schema.sql")

    if not os.path.exists(schema_path):
        print(f"ERROR: {schema_path} not found. Are you in the project root?")
        return

    with sqlite3.connect(DB_NAME) as conn:
        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()

    print(f"Database initialized: {DB_NAME}")
    print("Mock brand data loaded. Ready for agent use.")


def get_active_brand_campaigns() -> str:
    """Retrieve all active brand campaigns from the database.

    Use this tool when a creator wants to find brand sponsors,
    or when the agent needs to know what brands are looking for creators.

    Returns:
        A formatted string listing all brand campaigns with their
        industry, budget, target audience, and campaign brief.
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, industry, target_audience, budget_range, campaign_brief "
                "FROM brands ORDER BY name"
            )
            rows = cursor.fetchall()
    except sqlite3.OperationalError:
        return "Database not initialized. Run `python db_tools.py` first to set up the database."

    if not rows:
        return "No active brand campaigns found in the database."

    result = f"Found {len(rows)} active brand campaigns:\n\n"
    for name, industry, audience, budget, brief in rows:
        result += (
            f"Brand: {name}\n"
            f"  Industry: {industry}\n"
            f"  Budget: {budget}\n"
            f"  Brief: {brief}\n"
            f"  Target audience: {audience}\n\n"
        )
    return result


def save_match_result(
    brand_name: str,
    creator_id: str,
    creator_name: str,
    fit_score: int,
    match_reason: str,
) -> str:
    """Save a successful brand-creator match to the database.

    Call this after scoring confirms a good match. The match is stored
    for future reference and reporting.

    Args:
        brand_name: Name of the brand (must match a brand in the brands table)
        creator_id: YouTube channel ID of the matched creator
        creator_name: Display name of the creator's channel
        fit_score: Match quality score from 0 to 100
        match_reason: Brief explanation of why this is a good match

    Returns:
        Confirmation message that the match was saved.
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(
                "INSERT INTO matches (brand_name, creator_id, creator_name, fit_score, match_reason) "
                "VALUES (?, ?, ?, ?, ?)",
                (brand_name, creator_id, creator_name, fit_score, match_reason),
            )
            conn.commit()
    except sqlite3.OperationalError:
        return "Database not initialized. Run `python db_tools.py` first to set up the database."

    return (
        f"Match saved: {creator_name} ({creator_id}) matched with {brand_name} "
        f"(score: {fit_score}/100). Reason: {match_reason}"
    )


def get_match_history(brand_name: str = "") -> str:
    """Retrieve past match results from the database.

    Use this to show the user what matches have been made previously.
    Can filter by brand name or show all matches.

    Args:
        brand_name: Optional brand name to filter by. Leave empty for all matches.

    Returns:
        A formatted string listing past matches with scores and reasons.
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            if brand_name:
                cursor.execute(
                    "SELECT brand_name, creator_name, creator_id, fit_score, match_reason, created_at "
                    "FROM matches WHERE brand_name = ? ORDER BY created_at DESC",
                    (brand_name,),
                )
            else:
                cursor.execute(
                    "SELECT brand_name, creator_name, creator_id, fit_score, match_reason, created_at "
                    "FROM matches ORDER BY created_at DESC LIMIT 20"
                )
            rows = cursor.fetchall()
    except sqlite3.OperationalError:
        return "Database not initialized. Run `python db_tools.py` first to set up the database."

    if not rows:
        if brand_name:
            return f"No match history found for brand '{brand_name}'."
        return "No match history found. No matches have been saved yet."

    result = f"Match history ({len(rows)} results):\n\n"
    for brand, creator, cid, score, reason, date in rows:
        result += (
            f"[{date}] {brand} ↔ {creator}\n"
            f"  Channel: {cid} | Score: {score}/100\n"
            f"  Reason: {reason}\n\n"
        )
    return result


if __name__ == "__main__":
    init_db()