"""
calendar_mcp_server/server.py
─────────────────────────────
MCP server exposing 3 Google Calendar tools to the Scheduling Agent.

STUB mode  (USE_REAL_CALENDAR=false or env var not set)
Returns realistic fake data so the full agent flow works
end-to-end without any OAuth setup.

REAL mode  (USE_REAL_CALENDAR=true)
Uses a pre-generated token.json (from running auth_setup.py
once locally) stored as the env var CALENDAR_TOKEN_JSON.
No browser pop-up at runtime — safe for Cloud Run.

Tools exposed:
  • check_availability(date, duration_minutes, timezone)
  • create_meeting(title, date, time, duration_minutes, attendees, description)
  • list_upcoming_events(max_results)
"""

import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# CORRECT import: FastMCP is bundled inside the `mcp` package (mcp.server.fastmcp).
# Do NOT install the standalone `fastmcp` package — it's a different project and
# will conflict with google-adk's pinned mcp version.
from mcp.server.fastmcp import FastMCP

# ── initialise server ──────────────────────────────────────────────────────────
mcp = FastMCP("calendar-mcp-server")

# ── decide mode ────────────────────────────────────────────────────────────────
USE_REAL_CALENDAR = os.environ.get("USE_REAL_CALENDAR", "false").lower() == "true"
CALENDAR_TOKEN_JSON = os.environ.get("CALENDAR_TOKEN_JSON", "").strip()
REAL_CALENDAR_READY = USE_REAL_CALENDAR and bool(CALENDAR_TOKEN_JSON)


# ── helper: build real Google Calendar service ─────────────────────────────────
def _get_calendar_service():
    """
    Returns an authenticated Google Calendar API service object.

    Expects the environment variable CALENDAR_TOKEN_JSON to contain the
    full JSON string of a previously generated token.json file.

    To generate token.json the first time (run locally, NOT on Cloud Run):
        python auth_setup.py
    Then copy the contents of token.json into your Cloud Run env var.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    token_json_str = os.environ.get("CALENDAR_TOKEN_JSON")
    if not token_json_str:
        raise RuntimeError(
            "CALENDAR_TOKEN_JSON env var is not set. "
            "Run auth_setup.py locally to generate token.json, "
            "then store its contents in this env var."
        )

    token_data = json.loads(token_json_str)
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )

    # Auto-refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return build("calendar", "v3", credentials=creds)


# ── helper: compute end time from start hour and duration ──────────────────────
def _compute_end_time(start_hour: int, start_minute: int, duration_minutes: int) -> str:
    """Return HH:MM string for the end time, handling hour rollover correctly.

    Avoids the bug where duration_minutes (e.g. 60) was formatted directly
    into the minutes field, producing invalid times like '09:60'.
    """
    total_minutes = start_hour * 60 + start_minute + duration_minutes
    end_hour = (total_minutes // 60) % 24
    end_minute = total_minutes % 60
    return f"{end_hour:02d}:{end_minute:02d}"


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 1 — check_availability
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def check_availability(
    date: str,
    duration_minutes: int = 60,
    timezone: str = "Asia/Singapore",
) -> dict:
    """
    Check available time slots on a given date.

    Args:
        date: Date to check in YYYY-MM-DD format (e.g. "2026-04-01")
        duration_minutes: Length of the meeting in minutes (default 60)
        timezone: Timezone string (default "Asia/Singapore")

    Returns:
        dict with 'date', 'duration_minutes', 'available_slots' list,
        and 'timezone'.
    """
    if not REAL_CALENDAR_READY:
        # ── STUB ──────────────────────────────────────────────────────────────
        response = {
            "date": date,
            "duration_minutes": duration_minutes,
            "timezone": timezone,
            "available_slots": [
                "09:00", "10:00", "11:00",
                "14:00", "15:00", "16:00",
            ],
            "mode": "stub",
        }
        if USE_REAL_CALENDAR and not CALENDAR_TOKEN_JSON:
            response["warning"] = (
                "USE_REAL_CALENDAR=true but CALENDAR_TOKEN_JSON is missing; "
                "falling back to stub mode."
            )
        return response

    # ── REAL ──────────────────────────────────────────────────────────────────
    try:
        service = _get_calendar_service()

        # Build time range for the full day in the USER'S timezone,
        # then convert to RFC 3339 for the API (which accepts any tz offset).
        try:
            tz = ZoneInfo(timezone)
        except (KeyError, Exception):
            tz = ZoneInfo("Asia/Singapore")

        day_start_dt = datetime(
            *map(int, date.split("-")), hour=0, minute=0, tzinfo=tz
        )
        day_end_dt = day_start_dt.replace(hour=23, minute=59, second=59)

        day_start_iso = day_start_dt.isoformat()
        day_end_iso = day_end_dt.isoformat()

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=day_start_iso,
                timeMax=day_end_iso,
                timeZone=timezone,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        # Parse busy times into timezone-aware datetimes for correct comparison
        busy_times = []
        for event in events_result.get("items", []):
            start_str = event["start"].get("dateTime", "")
            end_str   = event["end"].get("dateTime", "")
            if start_str and end_str:
                busy_times.append({
                    "start": datetime.fromisoformat(start_str),
                    "end":   datetime.fromisoformat(end_str),
                })

        # Offer hourly slots from 09:00–17:00 that don't overlap busy times
        candidate_hours = [9, 10, 11, 13, 14, 15, 16]
        available_slots = []
        for hour in candidate_hours:
            slot_start_dt = day_start_dt.replace(hour=hour, minute=0, second=0)
            slot_end_dt = slot_start_dt + timedelta(minutes=duration_minutes)
            conflict = any(
                b["start"] < slot_end_dt and b["end"] > slot_start_dt
                for b in busy_times
            )
            if not conflict:
                available_slots.append(f"{hour:02d}:00")

        return {
            "date": date,
            "duration_minutes": duration_minutes,
            "timezone": timezone,
            "available_slots": available_slots,
            "mode": "real",
        }
    except Exception as e:
        return {"error": str(e), "available_slots": []}


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 2 — create_meeting
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def create_meeting(
    title: str,
    date: str,
    time: str,
    duration_minutes: int = 60,
    attendees: list[str] | None = None,
    description: str = "",
    timezone: str = "Asia/Singapore",
) -> dict:
    """
    Create a calendar event / intro call.

    Args:
        title: Meeting title (e.g. "EcoGlow x GreenBeautyVlog Intro Call")
        date: Date in YYYY-MM-DD format (e.g. "2026-04-01")
        time: Start time in HH:MM format, 24h (e.g. "10:00")
        duration_minutes: Duration in minutes (default 60)
        attendees: List of email addresses to invite (optional)
        description: Optional meeting description / agenda
        timezone: Timezone string (default "Asia/Singapore")

    Returns:
        dict with meeting details and a 'meet_link' if real mode.
    """
    if attendees is None:
        attendees = []

    if not REAL_CALENDAR_READY:
        # ── STUB ──────────────────────────────────────────────────────────────
        fake_id = f"stub_{date}_{time.replace(':', '')}_{title[:10].replace(' ', '_')}"
        response = {
            "status": "created",
            "meeting_id": fake_id,
            "title": title,
            "date": date,
            "time": time,
            "duration_minutes": duration_minutes,
            "attendees": attendees,
            "meet_link": "https://meet.google.com/stub-link-abc",
            "description": description,
            "timezone": timezone,
            "mode": "stub",
        }
        if USE_REAL_CALENDAR and not CALENDAR_TOKEN_JSON:
            response["warning"] = (
                "USE_REAL_CALENDAR=true but CALENDAR_TOKEN_JSON is missing; "
                "falling back to stub mode."
            )
        return response

    # ── REAL ──────────────────────────────────────────────────────────────────
    try:
        service = _get_calendar_service()

        hour, minute = map(int, time.split(":"))
        end_time = _compute_end_time(hour, minute, duration_minutes)
        start_dt = f"{date}T{time}:00"
        end_dt   = f"{date}T{end_time}:00"

        event_body = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_dt, "timeZone": timezone},
            "end":   {"dateTime": end_dt,   "timeZone": timezone},
            "conferenceData": {
                "createRequest": {
                    "requestId": f"sponsorship-bridge-{date}-{time}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
            "attendees": [{"email": e} for e in attendees],
        }

        created = (
            service.events()
            .insert(
                calendarId="primary",
                body=event_body,
                conferenceDataVersion=1,
                sendUpdates="all",
            )
            .execute()
        )

        meet_link = (
            created.get("conferenceData", {})
            .get("entryPoints", [{}])[0]
            .get("uri", "")
        )

        return {
            "status": "created",
            "meeting_id": created.get("id"),
            "title": title,
            "date": date,
            "time": time,
            "duration_minutes": duration_minutes,
            "attendees": attendees,
            "meet_link": meet_link,
            "calendar_link": created.get("htmlLink"),
            "mode": "real",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 3 — list_upcoming_events
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def list_upcoming_events(max_results: int = 5) -> dict:
    """
    List upcoming calendar events (useful to confirm scheduled meetings).

    Args:
        max_results: Maximum number of events to return (default 5)

    Returns:
        dict with an 'events' list, each item having title, start, end, attendees.
    """
    if not REAL_CALENDAR_READY:
        # ── STUB ──────────────────────────────────────────────────────────────
        today = datetime.now(timezone.utc).date()
        stub_events = [
            {
                "title": "EcoGlow x GreenBeautyVlog Intro Call",
                "start": f"{today + timedelta(days=2)}T10:00:00",
                "end":   f"{today + timedelta(days=2)}T11:00:00",
                "attendees": ["brand@ecoglow.com", "creator@greenbeautyvlog.com"],
                "meet_link": "https://meet.google.com/stub-link-abc",
            },
            {
                "title": "TechFlow x ProductivityPro Intro Call",
                "start": f"{today + timedelta(days=4)}T14:00:00",
                "end":   f"{today + timedelta(days=4)}T15:00:00",
                "attendees": ["brand@techflow.com", "creator@productivitypro.com"],
                "meet_link": "https://meet.google.com/stub-link-xyz",
            },
        ]
        response = {"events": stub_events[:max_results], "mode": "stub"}
        if USE_REAL_CALENDAR and not CALENDAR_TOKEN_JSON:
            response["warning"] = (
                "USE_REAL_CALENDAR=true but CALENDAR_TOKEN_JSON is missing; "
                "falling back to stub mode."
            )
        return response

    # ── REAL ──────────────────────────────────────────────────────────────────
    try:
        service = _get_calendar_service()
        now = datetime.now(timezone.utc).isoformat()

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = []
        for e in events_result.get("items", []):
            attendee_emails = [a.get("email", "") for a in e.get("attendees", [])]
            meet_link = (
                e.get("conferenceData", {})
                .get("entryPoints", [{}])[0]
                .get("uri", "")
            )
            events.append({
                "title":     e.get("summary", "(No title)"),
                "start":     e["start"].get("dateTime", e["start"].get("date")),
                "end":       e["end"].get("dateTime",   e["end"].get("date")),
                "attendees": attendee_emails,
                "meet_link": meet_link,
            })

        return {"events": events, "mode": "real"}
    except Exception as e:
        return {"events": [], "error": str(e)}


# ── entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
