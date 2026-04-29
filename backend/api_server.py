"""Sponsorship Bridge demo API and UI server.

The server prefers FastAPI when the project dependencies are installed. If
FastAPI is not available, it falls back to Python's built-in HTTP server with
the same demo endpoints. That keeps the hackathon UI runnable in lightweight
local environments.
"""

from __future__ import annotations

import json
import os
import importlib.util
import asyncio
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import sys
# ── Path setup ─────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).parent.resolve()
_PROJECT_ROOT = _THIS_DIR.parent.resolve()

# Insert root so 'sponsorship_bridge' and 'backend' can be imported
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
# Insert backend so 'db_tools' can be imported directly
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

try:
    from backend.db_tools import DB_NAME, get_active_brand_campaigns, init_db, save_match_result
except (ImportError, ModuleNotFoundError):
    from db_tools import DB_NAME, get_active_brand_campaigns, init_db, save_match_result

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    FASTAPI_AVAILABLE = False


APP_DIR = Path(__file__).parent
UI_DIR = APP_DIR.parent / "ui"
APP_NAME = "sponsorship_bridge"
_RUNNER = None
_SESSION_SERVICE = None

_SCORING_SPEC = importlib.util.spec_from_file_location(
    "sponsorship_bridge_scoring",
    APP_DIR.parent / "sponsorship_bridge" / "scoring.py",
)
if _SCORING_SPEC is None or _SCORING_SPEC.loader is None:
    raise RuntimeError("Could not load sponsorship_bridge/scoring.py")
_SCORING_MODULE = importlib.util.module_from_spec(_SCORING_SPEC)
_SCORING_SPEC.loader.exec_module(_SCORING_MODULE)
generate_media_kit = _SCORING_MODULE.generate_media_kit
score_creator_fit = _SCORING_MODULE.score_creator_fit
keyword_overlap = _SCORING_MODULE._keyword_overlap


@dataclass
class CreatorInput:
    creator_name: str
    channel_id: str = ""
    channel_url: str = ""
    subscribers: int = 0
    total_views: int = 0
    avg_views: int = 0
    content_topics: str = ""
    country: str = "Unknown"
    channel_description: str = ""
    recent_video_titles: str = ""
    recent_video_dates: str = ""
    video_count: int = 0
    shorts_ratio: float = 0.0
    total_likes_recent: int = 0
    total_comments_recent: int = 0
    total_views_recent: int = 0
    recent_videos: list[dict[str, Any]] | None = None


DEMO_CREATORS: list[CreatorInput] = [
    CreatorInput(
        creator_name="Beauty Within",
        channel_id="UC8f2CDyLibpGYSN3O2LfDwg",
        channel_url="https://www.youtube.com/@BeautyWithin",
        subscribers=2_710_000,
        total_views=168_500_000,
        avg_views=92_000,
        content_topics="skincare, beauty, self care, product reviews, wellness",
        country="US",
        channel_description=(
            "Beauty and skincare education channel covering product reviews, "
            "skin health, ingredient explainers, routines, and self-care."
        ),
        recent_video_titles=(
            "Dermatologist Reacts to Skincare Trends, Best Barrier Repair Products, "
            "Morning Skincare Routine, Clean Beauty Products Worth Trying"
        ),
        recent_video_dates="2026-04-12,2026-03-29,2026-03-15,2026-03-01",
        video_count=956,
        total_likes_recent=18_400,
        total_comments_recent=1_520,
        total_views_recent=368_000,
        recent_videos=[
            {"title": "THIS facial massage DEPUFFS & SCULPTS your face (chin, jawline, TMJ)", "url": "https://www.youtube.com/watch?v=K4EOJ2yGPC0"},
            {"title": "My 30s skin routine - what I do and don’t do now", "url": "https://www.youtube.com/watch?v=rnuYzwCdHRw"},
            {"title": "Drink THIS for hair growth - thick & shiny hair (3 easy recipes)", "url": "https://www.youtube.com/watch?v=kBXBg_lQXHA"},
        ],
    ),
    CreatorInput(
        creator_name="Shelbizleee",
        channel_id="UCv2LNRhF34_v1VNC08ZuooA",
        channel_url="https://www.youtube.com/@Shelbizleee",
        subscribers=395_000,
        total_views=58_500_000,
        avg_views=49_000,
        content_topics="sustainable living, zero waste, eco home, deinfluencing",
        country="US",
        channel_description=(
            "Sustainability education, low-waste swaps, thrifted home routines, "
            "deinfluencing, and realistic eco-friendly lifestyle experiments."
        ),
        recent_video_titles=(
            '"Must Haves" I DON\'T OWN, deinfluencing viral landfill decor, '
            "Are the viral meal prep cubes worth it, Eco Friendly Trends that Aged Terribly"
        ),
        recent_video_dates="2026-04-02,2026-03-25,2026-03-18,2026-03-04",
        video_count=765,
        total_likes_recent=12_500,
        total_comments_recent=1_454,
        total_views_recent=246_100,
        recent_videos=[
            {"title": '"Must Haves" I DON\'T OWN', "url": "https://www.youtube.com/watch?v=xo47807kkSM"},
            {"title": "deinfluencing viral landfill decor", "url": "https://www.youtube.com/watch?v=rgbdkql394s"},
            {"title": "are the viral MEAL PREP cubes worth it?", "url": "https://www.youtube.com/watch?v=dAiilZPWVHQ"},
        ],
    ),
    CreatorInput(
        creator_name="Gittemary Johansen",
        channel_id="UCFQ_CWYmt-ScWaPX4YfnBrQ",
        channel_url="https://www.youtube.com/channel/UCFQ_CWYmt-ScWaPX4YfnBrQ",
        subscribers=149_000,
        total_views=23_300_000,
        avg_views=18_800,
        content_topics="sustainable living, zero waste, vegan lifestyle, eco beauty",
        country="DK",
        channel_description=(
            "Zero-waste creator sharing eco-friendly beauty, sustainable living, "
            "low-waste habits, vegan lifestyle choices, and conscious consumption."
        ),
        recent_video_titles=(
            "Zero Waste Bathroom Reset, Sustainable Home Swaps That Last, "
            "Thrifted Kitchen Makeover, Vegan Self Care Routine"
        ),
        recent_video_dates="2026-04-17,2026-04-03,2026-03-20,2026-03-06",
        video_count=1_037,
        total_likes_recent=5_480,
        total_comments_recent=690,
        total_views_recent=92_000,
        recent_videos=[
            {"title": "9 unspoken rules of thrifting - stop making these mistakes when shopping second hand", "url": "https://www.youtube.com/watch?v=vxU0gDiTqqw"},
            {"title": "Who sends me gifts? Can I unbox PR gifts and still be an environmentalist?", "url": "https://www.youtube.com/watch?v=J3VGLyDwaOA"},
            {"title": "HIDDEN IN THE FABRIC - the danger no one is talking about", "url": "https://www.youtube.com/watch?v=WPzARYdfPVg"},
        ],
    ),
    CreatorInput(
        creator_name="CleanBeautyUS",
        channel_id="UCdemoCleanBeautyUS0004",
        subscribers=210_000,
        total_views=12_200_000,
        avg_views=12_000,
        content_topics="beauty, makeup, skincare reviews",
        country="US",
        channel_description=(
            "Drugstore and luxury beauty reviews, makeup wear tests, skincare "
            "empties, and occasional sponsored lifestyle content."
        ),
        recent_video_titles=(
            "Drugstore vs Luxury Skincare, Clean Beauty Myths Debunked, "
            "Monthly Empties, SPF Wear Test"
        ),
        recent_video_dates="2026-04-01,2026-03-09,2026-02-19,2026-01-25",
        video_count=176,
        total_likes_recent=1_540,
        total_comments_recent=160,
        total_views_recent=48_000,
        recent_videos=[
            {"title": "Drugstore vs Luxury Skincare", "url": "https://www.youtube.com/results?search_query=clean+beauty+drugstore+luxury+review"},
            {"title": "Clean Beauty Myths Debunked", "url": "https://www.youtube.com/results?search_query=clean+beauty+myths+debunked"},
            {"title": "SPF Wear Test", "url": "https://www.youtube.com/results?search_query=SPF+wear+test"},
        ],
    ),
]

DEMO_CREATOR_PROFILE = CreatorInput(
    creator_name="Mabel's Eco Creator Demo",
    channel_id="UCdemoCreatorMode0001",
    subscribers=149_000,
    total_views=23_360_000,
    avg_views=18_800,
    content_topics="sustainable living, zero waste, eco home, vegan lifestyle",
    country="US",
    channel_description=(
        "A YouTube creator making practical sustainable living, zero-waste "
        "routines, thrifted home ideas, and realistic eco-friendly product swaps."
    ),
    recent_video_titles=(
        "Zero Waste Bathroom Reset, Sustainable Home Swaps That Last, "
        "Thrifted Kitchen Makeover, Vegan Self Care Routine"
    ),
    recent_video_dates="2026-04-17,2026-04-03,2026-03-20,2026-03-06",
    video_count=178,
    total_likes_recent=5_480,
    total_comments_recent=690,
    total_views_recent=92_000,
    recent_videos=[
        {"title": "Zero Waste Bathroom Reset"},
        {"title": "Sustainable Home Swaps That Last"},
        {"title": "Vegan Self Care Routine"},
    ],
)


def _ensure_db() -> None:
    if not os.path.exists(DB_NAME):
        init_db()
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_dossier (
                session_id TEXT,
                item_type TEXT,
                item_id TEXT,
                name TEXT,
                data TEXT,
                PRIMARY KEY (session_id, item_type, item_id)
            )
        """)
        conn.commit()


def _creator_from_dict(data: dict[str, Any]) -> CreatorInput:
    allowed = CreatorInput.__dataclass_fields__.keys()
    return CreatorInput(**{key: data[key] for key in allowed if key in data})


def _youtube_search_url(query: str) -> str:
    return f"https://www.youtube.com/results?search_query={quote_plus(query)}"


def _channel_url(creator: CreatorInput) -> str:
    if creator.channel_url:
        return creator.channel_url
    if creator.channel_id and creator.channel_id.startswith("UC") and "demo" not in creator.channel_id.lower():
        return f"https://www.youtube.com/channel/{creator.channel_id}"
    return _youtube_search_url(f"{creator.creator_name} YouTube channel")


def _video_refs(creator: CreatorInput, limit: int = 3) -> list[dict[str, Any]]:
    if creator.recent_videos:
        videos = creator.recent_videos[:limit]
    else:
        titles = [
            title.strip()
            for title in creator.recent_video_titles.split(",")
            if title.strip()
        ][:limit]
        videos = [{"title": title} for title in titles]

    refs: list[dict[str, Any]] = []
    for video in videos:
        title = str(video.get("title") or "Recent video")
        url = video.get("url")
        video_id = video.get("video_id")
        if not url and video_id:
            url = f"https://www.youtube.com/watch?v={video_id}"
        if not url:
            url = _youtube_search_url(f"{creator.creator_name} {title}")
        refs.append({
            "title": title,
            "url": url,
            "views": video.get("views"),
            "likes": video.get("likes"),
            "comments": video.get("comments"),
        })
    return refs


def _score_creator(brand_brief: str, creator: CreatorInput) -> dict[str, Any]:
    payload = asdict(creator)
    payload.pop("channel_id", None)
    payload.pop("channel_url", None)
    payload.pop("total_views", None)
    payload.pop("recent_videos", None)
    score = score_creator_fit(brand_brief=brand_brief, **payload)
    score["channel_id"] = creator.channel_id
    score["channel_url"] = _channel_url(creator)
    score["content_topics"] = creator.content_topics
    score["recent_videos"] = _video_refs(creator)
    return score


def health_payload() -> dict[str, str]:
    return {"status": "ok"}


def _load_local_env() -> None:
    """Load .env without requiring python-dotenv."""
    env_path = APP_DIR.parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        if key:
            os.environ[key] = value


def _summarise_tool_call(name: str, args: dict[str, Any]) -> str:
    if name == "search_youtube_creators":
        return f"YouTube search: {args.get('query', '')}"
    if name == "get_channel_videos":
        return "Fetched recent videos, likes, comments, and views"
    if name == "get_channel_details":
        return "Fetched channel stats and topics"
    if name == "score_creator_fit":
        return f"Scored {args.get('creator_name', 'creator')}"
    if name == "generate_media_kit":
        return f"Built media kit for {args.get('creator_name', 'creator')}"
    if name == "save_match_result":
        return "Saved top match to SQLite"
    if name == "get_active_brand_campaigns":
        return "Loaded brand campaigns from SQLite"
    if name == "resolve_channel":
        return f"Resolved {args.get('identifier', 'channel')}"
    return name


def _event_parts(event: Any) -> list[Any]:
    content = getattr(event, "content", None)
    return list(getattr(content, "parts", None) or [])


def _get_runner() -> Any:
    """Lazy-load ADK only for the real agent endpoint."""
    global _RUNNER, _SESSION_SERVICE
    if _RUNNER is not None:
        return _RUNNER

    _load_local_env()
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE":
        # Prevent stale AI Studio keys from hijacking Vertex mode.
        os.environ.pop("GOOGLE_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from sponsorship_bridge.agent import root_agent

    _SESSION_SERVICE = InMemorySessionService()
    _RUNNER = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=_SESSION_SERVICE,
    )
    return _RUNNER


async def agent_run_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Run the real ADK agent and capture MCP/tool activity for the UI."""
    message = str(data.get("message") or "").strip()
    if not message:
        return {"error": "message is required", "activity": [], "agent_text": ""}

    try:
        from google.genai.types import Content, Part
    except ModuleNotFoundError as exc:
        return {
            "error": "google-adk is not installed in this environment.",
            "detail": str(exc),
            "activity": [],
            "agent_text": "",
        }

    runner = _get_runner()
    user_id = str(data.get("user_id") or "demo-user")
    session_id = str(data.get("session_id") or uuid.uuid4())

    try:
        await _SESSION_SERVICE.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception:
        pass

    activity: list[dict[str, str]] = []
    text_parts: list[str] = []
    # Structured results captured from function_response parts so the UI can
    # render the full editorial dossier for live agent runs, not just prose.
    scored_results: list[dict[str, Any]] = []
    live_media_kit: dict[str, Any] | None = None
    saved_message: str = ""
    # Lookups built from YouTube MCP tool responses.
    channels_by_title: dict[str, dict[str, Any]] = {}   # title -> {channel_id, channel_url, custom_url}
    channels_by_id:    dict[str, dict[str, Any]] = {}   # channel_id -> {title, channel_url, custom_url}
    videos_by_id:      dict[str, list[dict[str, Any]]] = {}  # channel_id -> [{title,url}, ...]
    # Track the channel_id argument of the most recent get_channel_videos / resolve_channel
    # call so we can attribute the subsequent function_response to a specific channel.
    pending_video_channel_id: str | None = None
    pending_resolve_identifier: str | None = None
    # Pair score_creator_fit function_calls with their responses so we know which
    # brand_brief each score was computed against (needed for creator-mode brand
    # ranking where the same creator is scored against every DB brand).
    pending_score_briefs: list[str] = []
    # Each entry: {"brand_brief": str, "score": <score_dict>}
    scored_with_brief: list[dict[str, Any]] = []

    def _unwrap_response(raw: Any) -> Any:
        """MCP tool responses arrive as JSON strings, sometimes wrapped in {result: ...}."""
        if isinstance(raw, dict):
            for key in ("result", "response", "content"):
                if key in raw:
                    inner = raw[key]
                    # MCP often returns content as [{type:"text", text:"<json>"}]
                    if isinstance(inner, list) and inner and isinstance(inner[0], dict):
                        text = inner[0].get("text")
                        if isinstance(text, str):
                            inner = text
                    if isinstance(inner, (dict, list, str)):
                        raw = inner
                        break
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                return raw
        return raw

    def _index_search_channels(payload: Any) -> None:
        if not isinstance(payload, dict):
            if os.environ.get("SPONSORSHIP_BRIDGE_DEBUG"):
                print(f"[capture] search_youtube_creators payload NOT dict: {type(payload)} — {str(payload)[:200]}")
            return
        channels = payload.get("channels", []) or []
        if os.environ.get("SPONSORSHIP_BRIDGE_DEBUG"):
            print(f"[capture] indexing {len(channels)} channels from search_youtube_creators")
        for entry in channels:
            if not isinstance(entry, dict):
                continue
            title = entry.get("title") or ""
            cid = entry.get("channel_id") or ""
            url = entry.get("channel_url") or (f"https://www.youtube.com/channel/{cid}" if cid.startswith("UC") else "")
            custom = entry.get("custom_url") or ""
            if custom and not custom.startswith("@") and "/" not in custom:
                custom_url = f"https://www.youtube.com/@{custom.lstrip('@')}"
            elif custom:
                custom_url = custom if custom.startswith("http") else f"https://www.youtube.com/{custom.lstrip('/')}"
            else:
                custom_url = ""
            meta = {
                "channel_id": cid,
                "title": title,
                "channel_url": custom_url or url,
            }
            # Index by title AND by case-folded title AND by several name normalizations
            # so we can correlate when the agent passes a slightly different creator_name.
            if title:
                channels_by_title[title] = meta
                channels_by_title[title.lower()] = meta
                # "PENN.SMITH.SKINCARE" -> "Penn Smith Skincare" and vice versa
                normalized = title.replace(".", " ").replace("_", " ").strip()
                if normalized and normalized != title:
                    channels_by_title[normalized] = meta
                    channels_by_title[normalized.lower()] = meta
            if cid:
                channels_by_id[cid] = meta

    def _index_channel_videos(payload: Any, channel_id: str | None) -> None:
        if not isinstance(payload, dict) or not channel_id:
            return
        videos = payload.get("videos") or []
        refs: list[dict[str, Any]] = []
        for v in videos[:3]:
            if not isinstance(v, dict):
                continue
            title = str(v.get("title") or "Recent video")
            url = v.get("url")
            vid = v.get("video_id")
            if not url and vid:
                url = f"https://www.youtube.com/watch?v={vid}"
            if not url:
                url = f"https://www.youtube.com/results?search_query={quote_plus(title)}"
            refs.append({"title": title, "url": url})
        if refs:
            videos_by_id[channel_id] = refs

    def _index_resolve_response(payload: Any) -> None:
        """resolve_channel returns the same shape as get_channel_details — a single channel."""
        if not isinstance(payload, dict):
            return
        title = payload.get("title") or ""
        cid = payload.get("channel_id") or ""
        url = payload.get("channel_url") or (f"https://www.youtube.com/channel/{cid}" if cid.startswith("UC") else "")
        if title or cid:
            meta = {"channel_id": cid, "title": title, "channel_url": url}
            if title:
                channels_by_title[title] = meta
            if cid:
                channels_by_id[cid] = meta

    user_message = Content(role="user", parts=[Part(text=message)])

    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message,
        ):
            for part in _event_parts(event):
                fc = getattr(part, "function_call", None)
                if fc is not None and getattr(fc, "name", None):
                    args = dict(getattr(fc, "args", {}) or {})
                    activity.append({
                        "tool": fc.name,
                        "summary": _summarise_tool_call(fc.name, args),
                    })
                    if fc.name == "get_channel_videos":
                        pending_video_channel_id = str(args.get("channel_id") or "")
                    elif fc.name == "resolve_channel":
                        pending_resolve_identifier = str(args.get("identifier") or "")
                    elif fc.name == "score_creator_fit":
                        pending_score_briefs.append(str(args.get("brand_brief") or ""))
                    continue
                fr = getattr(part, "function_response", None)
                if fr is not None and getattr(fr, "name", None):
                    payload = _unwrap_response(getattr(fr, "response", None))
                    name = fr.name
                    if name == "score_creator_fit" and isinstance(payload, dict):
                        if payload.get("fit_score", 0):
                            scored_results.append(payload)
                        # Pair this response with the brand_brief from its FC.
                        brief = pending_score_briefs.pop(0) if pending_score_briefs else ""
                        scored_with_brief.append({"brand_brief": brief, "score": payload})
                    elif name == "generate_media_kit" and isinstance(payload, dict):
                        live_media_kit = payload
                    elif name == "save_match_result":
                        saved_message = str(payload) if payload is not None else ""
                    elif name == "search_youtube_creators":
                        _index_search_channels(payload)
                    elif name == "get_channel_videos":
                        _index_channel_videos(payload, pending_video_channel_id)
                        pending_video_channel_id = None
                    elif name == "resolve_channel":
                        _index_resolve_response(payload)
                        pending_resolve_identifier = None
                    elif name == "get_channel_details":
                        # Same shape as resolve — a single channel profile.
                        _index_resolve_response(payload)
                    continue
                text = getattr(part, "text", None)
                if text:
                    text_parts.append(text)
    except Exception as exc:
        return {
            "error": "Agent run failed",
            "detail": str(exc),
            "activity": activity,
            "agent_text": "\n".join(text_parts).strip(),
            "session_id": session_id,
            "top_matches": [],
            "media_kit": None,
            "saved_message": "",
        }

    # Correlate channel metadata into scored results so the UI can render
    # proper channel links and recent-video pills on each card. Match by
    # creator_name using multiple normalization strategies.
    def _find_channel(name: str) -> dict | None:
        if not name:
            return None
        # Exact
        if name in channels_by_title:
            return channels_by_title[name]
        # Case-fold
        lower = name.lower()
        if lower in channels_by_title:
            return channels_by_title[lower]
        # Normalized (strip punctuation)
        normalized = name.replace(".", " ").replace("_", " ").strip()
        if normalized in channels_by_title:
            return channels_by_title[normalized]
        if normalized.lower() in channels_by_title:
            return channels_by_title[normalized.lower()]
        # Loose: compare with whitespace+punctuation stripped, case-insensitive
        def _squash(s: str) -> str:
            return "".join(c for c in s.lower() if c.isalnum())
        target = _squash(name)
        for t, m in channels_by_title.items():
            if _squash(t) == target:
                return m
        return None

    for row in scored_results:
        name = row.get("creator_name", "")
        meta = _find_channel(name)
        if os.environ.get("SPONSORSHIP_BRIDGE_DEBUG"):
            print(f"[capture] score row name={name!r} matched_channel={bool(meta)} "
                  f"(index has {len(channels_by_title)} titles, {len(channels_by_id)} ids)")
        if meta:
            cid = meta.get("channel_id", "")
            if meta.get("channel_url"):
                row.setdefault("channel_url", meta["channel_url"])
            if cid:
                row.setdefault("channel_id", cid)
                if cid in videos_by_id:
                    row.setdefault("recent_videos", videos_by_id[cid])

    # Dedupe by creator_name (agent may score the same creator twice),
    # keep the highest fit_score, rank top 3.
    dedup: dict[str, dict[str, Any]] = {}
    for row in scored_results:
        k = row.get("creator_name", "")
        if not k:
            continue
        if k not in dedup or row.get("fit_score", 0) > dedup[k].get("fit_score", 0):
            dedup[k] = row
    top_matches = sorted(dedup.values(), key=lambda r: r.get("fit_score", 0), reverse=True)[:3]

    if live_media_kit:
        name = live_media_kit.get("creator_name", "")
        meta = channels_by_title.get(name)
        if meta:
            cid = meta.get("channel_id", "")
            if meta.get("channel_url"):
                live_media_kit.setdefault("channel_url", meta["channel_url"])
            if cid and cid in videos_by_id:
                live_media_kit.setdefault("recent_videos", videos_by_id[cid])

    # ── Creator-mode brand correlation ────────────────────────────────────
    # When the agent scores a creator against every DB brand (creator mode),
    # each score_creator_fit response carries a fit_score but no brand identity.
    # We paired each response with its brand_brief arg; now match that brief
    # against the DB brands to build brand-shaped records for the UI.
    brand_matches: list[dict[str, Any]] = []
    try:
        db_brands = _brand_rows()
    except Exception:
        db_brands = []
    if db_brands and scored_with_brief:
        def _brief_overlap(a: str, b: str) -> int:
            tokens_a = {w.strip(".,;:!?").lower() for w in a.split() if len(w) > 3}
            tokens_b = {w.strip(".,;:!?").lower() for w in b.split() if len(w) > 3}
            return len(tokens_a & tokens_b)

        seen_brands: set[str] = set()
        for pair in scored_with_brief:
            brief = pair["brand_brief"]
            score = pair["score"] or {}
            if not brief or not isinstance(score, dict) or not score.get("fit_score"):
                continue
            # Find the DB brand whose campaign_brief shares the most tokens.
            best = None
            best_overlap = 0
            for brand in db_brands:
                ov = _brief_overlap(brief, brand["campaign_brief"])
                if ov > best_overlap:
                    best_overlap = ov
                    best = brand
            if not best or best_overlap < 3:
                continue
            if best["name"] in seen_brands:
                continue
            seen_brands.add(best["name"])
            # Reconstruct a minimal CreatorInput from the score record so the
            # brand-centric "why" copy gets the creator's name and stats right.
            creator_stub = CreatorInput(
                creator_name=score.get("creator_name", ""),
                subscribers=score.get("subscribers", 0),
                content_topics=score.get("content_topics", ""),
            )
            # Derive relevance_01 from the relevance score component (max 20 pts).
            rel_pts = next(
                (c["points"] for c in score.get("score_components", []) if c.get("key") == "relevance"),
                0
            )
            relevance_01 = min((rel_pts or 0) / 20.0, 1.0)
            brand_matches.append({
                "brand_name": best["name"],
                "industry": best["industry"],
                "budget_range": best["budget_range"],
                "target_audience": best["target_audience"],
                "campaign_brief": best["campaign_brief"],
                "description": best.get("description", ""),
                "fit_score": score.get("fit_score", 0),
                "confidence": score.get("confidence", "medium"),
                "engagement_rate": score.get("engagement_rate", "N/A"),
                "why": _brand_why(best, creator_stub, score, relevance_01),
                "creator_reasoning": score.get("reasoning", ""),
                "pitch_angle": _pitch_angle(best["industry"], creator_stub),
                "risks": score.get("risk_flags", []) or ["Low risk"],
            })
        brand_matches.sort(key=lambda r: r.get("fit_score", 0), reverse=True)
        brand_matches = brand_matches[:3]

    return {
        "activity": activity,
        "agent_text": "\n".join(text_parts).strip(),
        "session_id": session_id,
        "top_matches": top_matches,
        "brand_matches": brand_matches,
        "media_kit": live_media_kit,
        "saved_message": saved_message,
    }



def outreach_draft_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Generate a personalized outreach DM from a brand to a creator.

    Honest framing: we produce a *draft* the user can copy and paste into
    whichever channel they actually use to reach the creator (channel About
    page, business inquiry form, agency rep). YouTube Data API does not
    expose creator emails, so this endpoint deliberately does not pretend
    to send anything.
    """
    brand_name = str(data.get("brand_name") or "").strip()
    brand_brief = str(data.get("brand_brief") or "").strip()
    creator_name = str(data.get("creator_name") or "").strip()
    creator_topics = str(data.get("creator_topics") or "").strip()
    recent_video_titles = str(data.get("recent_video_titles") or "").strip()
    match_reasoning = str(data.get("match_reasoning") or "").strip()
    sender_first_name = str(data.get("sender_first_name") or "").strip() or "Mabel"

    if not brand_name or not creator_name:
        return {"error": "brand_name and creator_name are required", "draft": ""}

    direction = str(data.get("mode") or "brand_to_creator").strip()

    if direction == "creator_to_brand":
        # The creator is pitching themselves to the brand.
        prompt = f"""You are drafting a sponsorship pitch DM from a YouTube creator to a brand.

Creator: {creator_name}
Creator content focus: {creator_topics}
Creator recent video titles: {recent_video_titles}
Brand: {brand_name}
Brand campaign brief: {brand_brief}
Why this brand is a good fit: {match_reasoning}

Write the DM. Requirements:
- Open by addressing the brand by name and explaining you've been following their work
- Briefly introduce yourself as a creator in one sentence (your niche / audience size)
- Reference ONE specific aspect of the brand's offering and explain why it fits your audience
- Propose a specific collaboration format (long-form integration, dedicated review, etc.) — match what the brand seems to want
- Suggest a short intro call as the next step
- Sign off with the sender's first name only: {sender_first_name}
- 80-110 words total, split into 2 short paragraphs separated by a blank line
- Conversational and professional, not fawning or transactional
- No bullet points, no headers, no markdown — just the message body

Return ONLY the message text. No preamble, no explanations, no quotes around it."""
    else:
        # Brand-to-creator (default).
        prompt = f"""You are drafting a sponsorship outreach DM from a brand to a YouTube creator.

Brand: {brand_name}
Brand campaign brief: {brand_brief}
Creator: {creator_name}
Creator content focus: {creator_topics}
Creator recent video titles: {recent_video_titles}
Why this creator was matched: {match_reasoning}

Write the DM. Requirements:
- Open by referencing ONE specific recent video by title (pick the strongest match)
- Briefly introduce the brand in one sentence (what they make / who it is for)
- Propose a specific collaboration format (long-form integration, dedicated review, etc.) — match the brand's brief
- Suggest a short intro call as the next step
- Sign off with the sender's first name only: {sender_first_name}
- 80-110 words total, split into 2 short paragraphs separated by a blank line
- Conversational and professional, not corporate jargon
- No bullet points, no headers, no markdown — just the message body

Return ONLY the message text. No preamble, no explanations, no quotes around it."""

    try:
        _load_local_env()
        # Prefer Vertex AI if configured (matches the rest of the app), else AI Studio.
        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE":
            os.environ.pop("GOOGLE_API_KEY", None)
            os.environ.pop("GEMINI_API_KEY", None)
            from google import genai
            client = genai.Client(
                vertexai=True,
                project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "europe-west1"),
            )
        else:
            from google import genai
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
            client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        draft = (response.text or "").strip()
        # Strip stray surrounding quotes some models add.
        if (draft.startswith('"') and draft.endswith('"')) or (draft.startswith('"') and draft.endswith('"')):
            draft = draft[1:-1].strip()
    except Exception as exc:
        print(f"ERROR in outreach_draft_payload: {exc}")
        return {"error": f"Outreach draft failed: {str(exc)}", "draft": ""}

    return {
        "brand_name": brand_name,
        "creator_name": creator_name,
        "draft": draft,
    }


def get_dossier_payload(data: dict[str, Any]) -> dict[str, Any]:
    session_id = data.get("session_id", "default")
    _ensure_db()
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT item_type, item_id, name, data FROM session_dossier WHERE session_id = ?",
            (session_id,)
        ).fetchall()
    
    items = []
    for r in rows:
        items.append({
            "type": r["item_type"],
            "id": r["item_id"],
            "name": r["name"],
            "data": json.loads(r["data"]) if r["data"] else {}
        })
    return {"items": items}


def add_dossier_payload(data: dict[str, Any]) -> dict[str, Any]:
    session_id = data.get("session_id", "default")
    item_type = data.get("type")
    item_id = data.get("id")
    name = data.get("name")
    item_data = data.get("data")
    
    if not all([item_type, item_id, name]):
        return {"error": "Missing item info"}
        
    _ensure_db()
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO session_dossier (session_id, item_type, item_id, name, data) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, item_type, item_id, name, json.dumps(item_data))
        )
        conn.commit()
    return {"status": "ok"}


def remove_dossier_payload(data: dict[str, Any]) -> dict[str, Any]:
    session_id = data.get("session_id", "default")
    item_type = data.get("type")
    item_id = data.get("id")
    clear_all = data.get("clear_all", False)
    
    _ensure_db()
    with sqlite3.connect(DB_NAME) as conn:
        if clear_all:
            conn.execute("DELETE FROM session_dossier WHERE session_id = ?", (session_id,))
        else:
            conn.execute(
                "DELETE FROM session_dossier WHERE session_id = ? AND item_type = ? AND item_id = ?",
                (session_id, item_type, item_id)
            )
        conn.commit()
    return {"status": "ok"}


def custom_prompt_payload(data: dict[str, Any]) -> dict[str, Any]:
    instruction = data.get("instruction", "").strip()
    session_id = data.get("session_id", "default")
    
    if not instruction:
        return {"error": "Instruction is required"}
        
    dossier = get_dossier_payload({"session_id": session_id})
    items = dossier.get("items", [])
    
    if not items:
        return {"error": "Dossier is empty. Add some creators or brands first."}
        
    context_parts = []
    for item in items:
        context_parts.append(f"- {item['type'].capitalize()}: {item['name']}")
    context_str = "\n".join(context_parts)
    
    prompt = f"""You are an expert sponsorship consultant helping a user with their workflow.
The user has selected the following creators and brands in their "Dossier":
{context_str}

The user's instruction is: "{instruction}"

Please provide a helpful, professional, and tailored response based on these selections. 
If the user asks for a draft, provide a high-quality draft.
If they ask for advice, give strategic advice.
If they ask for a campaign idea, be creative.

Requirements:
- Use the Newsreader font style (premium, editorial).
- Be concise but thorough.
- Do not use markdown headers, use bold text instead.
- Return ONLY the response text.
"""

    try:
        _load_local_env()
        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE":
            os.environ.pop("GOOGLE_API_KEY", None)
            os.environ.pop("GEMINI_API_KEY", None)
            from google import genai
            client = genai.Client(
                vertexai=True,
                project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "europe-west1"),
            )
        else:
            from google import genai
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
            client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        result = (response.text or "").strip()
    except Exception as exc:
        print(f"ERROR in custom_prompt_payload: {exc}")
        return {"error": f"Custom prompt generation failed: {str(exc)}"}
        
    return {"result": result}


def brands_payload() -> dict[str, str]:
    _ensure_db()
    return {"campaigns": get_active_brand_campaigns()}


def _brand_rows() -> list[dict[str, Any]]:
    _ensure_db()
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        # `description` may not exist in legacy DBs; fall back gracefully.
        try:
            rows = conn.execute(
                "SELECT name, industry, target_audience, budget_range, "
                "campaign_brief, description FROM brands ORDER BY name"
            ).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                "SELECT name, industry, target_audience, budget_range, campaign_brief "
                "FROM brands ORDER BY name"
            ).fetchall()
    return [dict(row) for row in rows]


def _brand_why(brand: dict[str, Any], creator: CreatorInput, score: dict[str, Any], relevance_01: float) -> str:
    """Brand-centric explanation for a creator-mode match card.

    Leads with the brand's own voice (the `description` field), then a single
    succinct sentence about how the creator fits — never the other way around.
    Falls back to a constructed sentence if no description is available.
    """
    # Verdict band based on the deterministic fit score.
    fit = float(score.get("fit_score", 0))
    if fit >= 75:
        verdict = "strong fit"
    elif fit >= 55:
        verdict = "moderate fit"
    elif fit >= 35:
        verdict = "partial fit"
    else:
        verdict = "limited fit"

    eng = score.get("engagement_rate", "N/A")
    creator_label = creator.creator_name or "Your channel"
    overlap_pct = round(relevance_01 * 100)
    fit_sentence = (
        f"{creator_label} ({score.get('subscribers', 0):,} subs, {eng} engagement, "
        f"{overlap_pct}% topical overlap) is a {verdict} for this campaign."
    )
    return fit_sentence  # description is rendered separately in the right panel


def _creator_relevance_01(brand_brief: str, creator: CreatorInput) -> float:
    creator_text = " ".join([
        creator.content_topics,
        creator.channel_description,
        creator.recent_video_titles,
    ])
    return min(keyword_overlap(brand_brief, creator_text), 10) / 10


def score_payload(data: dict[str, Any]) -> dict[str, Any]:
    _ensure_db()
    brand_name = str(data.get("brand_name") or "Demo Brand")
    brand_brief = str(data.get("brand_brief") or "").strip()
    if not brand_brief:
        return {"error": "brand_brief is required", "top_matches": []}

    raw_creators = data.get("creators")
    creators = (
        [_creator_from_dict(item) for item in raw_creators]
        if isinstance(raw_creators, list) and raw_creators
        else DEMO_CREATORS
    )

    scored = [_score_creator(brand_brief, creator) for creator in creators]
    scored = [item for item in scored if item.get("fit_score", 0) > 0]
    scored.sort(key=lambda item: item["fit_score"], reverse=True)
    top_matches = scored[:3]

    media_kit = None
    saved_message = ""
    if top_matches:
        best = top_matches[0]
        source = next(
            creator for creator in creators
            if creator.creator_name == best["creator_name"]
        )
        media_kit = generate_media_kit(
            creator_name=source.creator_name,
            channel_id=source.channel_id,
            subscribers=source.subscribers,
            total_views=source.total_views,
            avg_views=source.avg_views,
            top_topics=source.content_topics,
            country=source.country,
            recent_video_titles=source.recent_video_titles,
            video_count=source.video_count,
            engagement_rate=best.get("engagement_rate", ""),
        )
        media_kit["channel_url"] = _channel_url(source)
        media_kit["recent_videos"] = _video_refs(source)
        if data.get("save_top_match", True):
            saved_message = save_match_result(
                brand_name=brand_name,
                creator_id=source.channel_id,
                creator_name=source.creator_name,
                fit_score=int(round(float(best["fit_score"]))),
                match_reason=best.get("reasoning", "")[:500],
            )

    return {
        "brand_name": brand_name,
        "top_matches": top_matches,
        "media_kit": media_kit,
        "saved_message": saved_message,
        "scoring_note": "Engagement is calculated as (likes + comments) / views when recent video totals are available.",
    }


def creator_match_payload(data: dict[str, Any]) -> dict[str, Any]:
    creator_data = data.get("creator")
    creator = (
        _creator_from_dict(creator_data)
        if isinstance(creator_data, dict) and creator_data
        else DEMO_CREATOR_PROFILE
    )

    matches: list[dict[str, Any]] = []
    for brand in _brand_rows():
        score = _score_creator(brand["campaign_brief"], creator)
        relevance_01 = _creator_relevance_01(brand["campaign_brief"], creator)
        opportunity_score = round((score["fit_score"] * 0.70) + (relevance_01 * 30), 1)
        risk_flags = score.get("risk_flags") or []
        matches.append({
            "brand_name": brand["name"],
            "industry": brand["industry"],
            "budget_range": brand["budget_range"],
            "target_audience": brand["target_audience"],
            "campaign_brief": brand["campaign_brief"],
            "description": brand.get("description", ""),
            "fit_score": opportunity_score,
            "base_fit_score": score["fit_score"],
            "relevance_score": round(relevance_01 * 100),
            "confidence": score["confidence"],
            "engagement_rate": score["engagement_rate"],
            # Brand-centric explanation, NOT score_creator_fit's creator-shaped reasoning.
            "why": _brand_why(brand, creator, score, relevance_01),
            "creator_reasoning": score["reasoning"],  # kept for debug / advanced UIs
            "pitch_angle": _pitch_angle(brand["industry"], creator),
            "risks": risk_flags if risk_flags else ["Low risk"],
        })

    matches.sort(key=lambda item: item["fit_score"], reverse=True)
    media_kit = generate_media_kit(
        creator_name=creator.creator_name,
        channel_id=creator.channel_id,
        subscribers=creator.subscribers,
        total_views=creator.total_views,
        avg_views=creator.avg_views,
        top_topics=creator.content_topics,
        country=creator.country,
        recent_video_titles=creator.recent_video_titles,
        video_count=creator.video_count,
        engagement_rate=matches[0]["engagement_rate"] if matches else "",
    )
    media_kit["channel_url"] = _channel_url(creator)
    media_kit["recent_videos"] = _video_refs(creator)
    return {
        "creator_name": creator.creator_name,
        "brand_matches": matches[:3],
        "media_kit": media_kit,
        "scoring_note": "Creator mode reverses the match: the same scoring engine ranks SQLite brand campaigns for this creator.",
    }


def _pitch_angle(industry: str, creator: CreatorInput) -> str:
    topics = creator.content_topics.lower()
    industry_lower = (industry or "").lower()
    if "beauty" in industry_lower or "skincare" in industry_lower:
        return "Frame the integration as a values-led self-care routine, with honest before/after usage and ingredient fit."
    if "home" in industry_lower:
        return "Build a practical home reset episode around durable swaps, organization, and everyday sustainability."
    if "travel" in industry_lower:
        return "Pitch a conscious travel mini-series focused on low-waste packing, local stays, and experience quality."
    if "fitness" in industry_lower:
        return "Connect the brand to realistic healthy habits, nutrition routines, and creator-tested product use."
    if "technology" in industry_lower or "tech" in topics:
        return "Use a workflow or desk setup story showing how the product improves daily productivity."
    return "Pitch an authentic creator-led test: problem, product experience, honest result, and audience takeaway."


if FASTAPI_AVAILABLE:
    app = FastAPI(title="Sponsorship Bridge Demo API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return health_payload()

    @app.get("/api/brands")
    def brands() -> dict[str, str]:
        return brands_payload()

    @app.post("/api/score")
    def score(req: dict[str, Any]) -> dict[str, Any]:
        return score_payload(req)

    @app.post("/api/creator-match")
    def creator_match(req: dict[str, Any]) -> dict[str, Any]:
        return creator_match_payload(req)

    @app.post("/api/agent-run")
    async def agent_run(req: dict[str, Any]) -> dict[str, Any]:
        return await agent_run_payload(req)

    @app.post("/api/outreach-draft")
    def outreach_draft(req: dict[str, Any]) -> dict[str, Any]:
        return outreach_draft_payload(req)

    @app.get("/api/dossier")
    def get_dossier(session_id: str = "default") -> dict[str, Any]:
        return get_dossier_payload({"session_id": session_id})

    @app.post("/api/dossier")
    def add_dossier(req: dict[str, Any]) -> dict[str, Any]:
        return add_dossier_payload(req)

    @app.delete("/api/dossier")
    def remove_dossier(req: dict[str, Any]) -> dict[str, Any]:
        return remove_dossier_payload(req)

    @app.post("/api/custom-prompt")
    def custom_prompt(req: dict[str, Any]) -> dict[str, Any]:
        return custom_prompt_payload(req)

    if UI_DIR.exists():
        app.mount("/ui", StaticFiles(directory=str(UI_DIR)), name="ui")

    if UI_DIR.exists():
        @app.get("/")
        def root() -> FileResponse:
            return FileResponse(UI_DIR / "index.html")

        # Mount root to UI_DIR for assets (CSS, JS)
        app.mount("/", StaticFiles(directory=str(UI_DIR)), name="ui")
else:
    app = None


class BasicHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send_json(health_payload())
            return
        if self.path == "/api/brands":
            self._send_json(brands_payload())
            return
        if self.path.startswith("/api/dossier"):
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            session_id = qs.get("session_id", ["default"])[0]
            self._send_json(get_dossier_payload({"session_id": session_id}))
            return
        if self.path in {"/", "/index.html", "/ui/index.html"}:
            path = UI_DIR / "index.html"
        else:
            path = UI_DIR / self.path.lstrip("/")

        if path.exists() and path.is_file():
            body = path.read_bytes()
            ext = path.suffix.lower()
            ctype = "text/plain"
            if ext == ".html": ctype = "text/html; charset=utf-8"
            elif ext == ".css": ctype = "text/css"
            elif ext == ".js": ctype = "application/javascript"
            elif ext == ".ico": ctype = "image/x-icon"
            
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404)

    def do_POST(self) -> None:
        if self.path not in {"/api/score", "/api/creator-match", "/api/agent-run", "/api/outreach-draft", "/api/dossier", "/api/custom-prompt"}:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, status=400)
            return
        if self.path == "/api/agent-run":
            self._send_json(asyncio.run(agent_run_payload(data)))
        elif self.path == "/api/creator-match":
            self._send_json(creator_match_payload(data))
        elif self.path == "/api/outreach-draft":
            self._send_json(outreach_draft_payload(data))
        elif self.path == "/api/dossier":
            self._send_json(add_dossier_payload(data))
        elif self.path == "/api/custom-prompt":
            self._send_json(custom_prompt_payload(data))
        else:
            self._send_json(score_payload(data))

    def do_DELETE(self) -> None:
        if self.path != "/api/dossier":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, status=400)
            return
        self._send_json(remove_dossier_payload(data))


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    if FASTAPI_AVAILABLE:
        import uvicorn

        uvicorn.run("api_server:app", host=host, port=port, reload=False)
    else:
        server = ThreadingHTTPServer((host, port), BasicHandler)
        print(f"Sponsorship Bridge UI: http://{host}:{port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
