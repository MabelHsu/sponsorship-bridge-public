"""
YouTube MCP Server for Sponsorship Bridge
──────────────────────────────────────────
Exposes YouTube Data API v3 as 4 MCP tools via stdio transport.

Design: This server is a DATA-QUALITY LAYER. It handles API calls, error
handling, safe parsing, and filters out objectively bad data (zero subs,
zero videos, hidden stats). It does NOT filter on relevance — YouTube's
search API already returns relevant results, and the agent's score_creator_fit
handles relevance scoring with synonym expansion and keyword overlap.

Tools:
  • search_youtube_creators  — search for channels matching a query
  • get_channel_details      — fetch stats for a specific channel
  • get_channel_videos       — get recent videos with engagement metrics
  • resolve_channel          — resolve @handle, custom URL, or name → channel ID

Import: from mcp.server.fastmcp import FastMCP  (bundled with google-adk)
"""

import json
import os
import re
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from mcp.server.fastmcp import FastMCP

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
BASE_URL = "https://www.googleapis.com/youtube/v3"
MIN_SUBSCRIBERS = 1_000
_CACHE_MAX_ENTRIES = int(os.getenv("YOUTUBE_CACHE_MAX_ENTRIES", "256"))
_TTL_BY_ENDPOINT = {"search": 300, "channels": 600, "videos": 600}
_CACHE: OrderedDict[tuple, tuple[float, dict]] = OrderedDict()
_CACHE_HITS = 0
_CACHE_MISSES = 0

mcp = FastMCP("youtube-data-api")


# ── Helpers ────────────────────────────────────────────────────────────────

def _cache_key(endpoint: str, params: dict) -> tuple:
    return (endpoint, tuple(sorted((k, str(v)) for k, v in params.items() if k != "key")))


def _yt_get(endpoint: str, params: dict) -> dict:
    """Call YouTube Data API v3 and return parsed JSON.

    Successful responses are cached briefly in memory. This protects live demos
    from quota burn when judges retry the same prompt or switch back and forth
    between examples.
    """
    global _CACHE_HITS, _CACHE_MISSES

    safe_params = dict(params)
    key = _cache_key(endpoint, safe_params)
    now = time.time()
    cached = _CACHE.get(key)
    if cached:
        expires_at, value = cached
        if expires_at > now:
            _CACHE_HITS += 1
            _CACHE.move_to_end(key)
            return value
        _CACHE.pop(key, None)

    _CACHE_MISSES += 1
    safe_params["key"] = YOUTUBE_API_KEY
    try:
        resp = httpx.get(f"{BASE_URL}/{endpoint}", params=safe_params, timeout=15.0)
        if resp.status_code == 403:
            return {"error": "YouTube API quota exceeded or key invalid. Check your YOUTUBE_API_KEY."}
        resp.raise_for_status()
        data = resp.json()
        if "error" not in data:
            ttl = _TTL_BY_ENDPOINT.get(endpoint, 300)
            _CACHE[key] = (now + ttl, data)
            _CACHE.move_to_end(key)
            while len(_CACHE) > _CACHE_MAX_ENTRIES:
                _CACHE.popitem(last=False)
        return data
    except httpx.HTTPStatusError as e:
        return {"error": f"YouTube API HTTP error {e.response.status_code}: {e.response.text[:200]}"}
    except httpx.RequestError as e:
        return {"error": f"YouTube API request failed: {str(e)}"}


def _safe_int(value, default: int = 0) -> int:
    """Parse YouTube numeric strings safely (handles None, missing, non-numeric)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalise_topic_labels(topic_categories: Iterable[str]) -> list[str]:
    """Convert YouTube topic category URLs into readable short labels.
    e.g. "https://en.wikipedia.org/wiki/Clean_Beauty" → "clean beauty"
    """
    labels: list[str] = []
    for url in topic_categories or []:
        tail = str(url).rstrip("/").split("/")[-1]
        tail = tail.replace("_", " ").replace("-", " ").strip().lower()
        if tail:
            labels.append(tail)
    return labels


def _recent_cutoff_iso(days: int = 365) -> str:
    """Return RFC 3339 UTC timestamp N days ago (for publishedAfter API param)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return cutoff.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_short_duration(duration_iso: str) -> bool:
    """Check if an ISO 8601 duration (e.g. PT45S, PT1M2S) is <= 60 seconds.

    YouTube Shorts are vertical videos of 60 seconds or less.
    """
    if not duration_iso:
        return False
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_iso)
    if not m:
        return False
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return 0 < total_seconds <= 60


def _expand_queries(base_query: str) -> list[str]:
    """Generate query variants.

    Demo default is intentionally conservative: one search call per tool call.
    Set YOUTUBE_QUERY_VARIANTS=true when you want broader discovery and have
    quota headroom.
    """
    base = base_query.strip()
    use_variants = os.getenv("YOUTUBE_QUERY_VARIANTS", "false").strip().lower()
    if use_variants in {"1", "true", "yes", "on"}:
        return [base, f"{base} channel", f"{base} review"]
    return [base]


def _parse_youtube_url(input_str: str):
    """Parse a YouTube URL, tolerating missing schemes."""
    candidate = input_str.strip()
    if "://" not in candidate and candidate.lower().startswith(("www.", "youtube.com/", "m.youtube.com/")):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    hostname = (parsed.netloc or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    if hostname.startswith("m."):
        hostname = hostname[2:]

    if hostname not in {"youtube.com", "youtu.be"}:
        return None
    return parsed


def _extract_handle(input_str: str) -> str | None:
    """Extract a YouTube @handle from a URL or plain @handle string.

    Accepts:
      - https://www.youtube.com/@handle
      - https://youtube.com/@handle
      - @handle
      - youtube.com/@handle

    Returns the handle WITHOUT the @ prefix, or None if no handle found.
    """
    input_str = input_str.strip()

    # Direct @handle
    m = re.match(r'^@([\w.-]+)$', input_str)
    if m:
        return m.group(1)

    # URL with @handle
    m = re.search(r'youtube\.com/@([\w.-]+)', input_str)
    if m:
        return m.group(1)

    parsed = _parse_youtube_url(input_str)
    if parsed:
        path = unquote(parsed.path or "").strip("/")
        if path.startswith("@"):
            handle = path[1:].split("/")[0].strip()
            if handle:
                return handle

    return None


def _extract_channel_id(input_str: str) -> str | None:
    """Extract a UC... channel ID from a URL or plain ID string."""
    input_str = input_str.strip()

    # Direct channel ID
    if re.match(r'^UC[\w-]{22}$', input_str):
        return input_str

    # URL with /channel/UC...
    m = re.search(r'youtube\.com/channel/(UC[\w-]{22})', input_str)
    if m:
        return m.group(1)

    parsed = _parse_youtube_url(input_str)
    if parsed:
        path = unquote(parsed.path or "").strip("/")
        if path.startswith("channel/"):
            parts = path.split("/")
            if len(parts) >= 2 and re.match(r"^UC[\w-]{22}$", parts[1]):
                return parts[1]

    return None


def _extract_legacy_username(input_str: str) -> str | None:
    """Extract usernames from /user/... and /c/... URLs, or plain names."""
    parsed = _parse_youtube_url(input_str)
    if parsed:
        path = unquote(parsed.path or "").strip("/")
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"user", "c"}:
            return parts[1]

        query = parse_qs(parsed.query)
        if "channel_id" in query and query["channel_id"]:
            return query["channel_id"][0]

    m = re.search(r"youtube\.com/user/([\w.-]+)", input_str)
    if m:
        return m.group(1)

    if re.match(r"^[\w .-]+$", input_str) and not input_str.startswith(("UC", "@")):
        return input_str.strip()

    return None


def _build_search_term(identifier: str, handle: str | None = None) -> str:
    """Convert a pasted identifier or URL into a cleaner search term."""
    parsed = _parse_youtube_url(identifier)
    if parsed:
        path = unquote(parsed.path or "").strip("/")
        parts = [part for part in path.split("/") if part]

        if parts:
            if parts[0].startswith("@"):
                return parts[0][1:]
            if parts[0] in {"channel", "user", "c"} and len(parts) >= 2:
                return parts[1]
            if parts[0] in {"watch", "playlist", "shorts", "live"}:
                return handle or ""
            return parts[-1]

    search_term = re.sub(r"https?://[^\s]*", "", identifier).strip()
    search_term = search_term.lstrip("@").strip()
    if not search_term and handle:
        search_term = handle
    return search_term or identifier.strip()


def _build_channel_dict(ch: dict) -> dict:
    """Build a standardized channel dict from a YouTube API channel resource.

    Handles channels that hide their subscriber count by setting
    subscribers to -1 and adding a hidden_subscribers flag.
    """
    stats = ch.get("statistics", {})
    snippet = ch.get("snippet", {})
    topic_categories = ch.get("topicDetails", {}).get("topicCategories", [])
    branding = ch.get("brandingSettings", {}).get("channel", {})
    keywords = branding.get("keywords", "")

    hidden_subs = stats.get("hiddenSubscriberCount", False)
    subscribers = -1 if hidden_subs else _safe_int(stats.get("subscriberCount"))

    result = {
        "channel_id": ch["id"],
        "title": snippet.get("title", ""),
        "description": snippet.get("description", "")[:1_000],
        "country": snippet.get("country", "Unknown"),
        "custom_url": snippet.get("customUrl", ""),
        "subscribers": subscribers,
        "total_views": _safe_int(stats.get("viewCount")),
        "video_count": _safe_int(stats.get("videoCount")),
        "topics": topic_categories,
        "topic_labels": _normalise_topic_labels(topic_categories),
        "keywords": keywords,
        "channel_url": f"https://www.youtube.com/channel/{ch['id']}",
    }
    if hidden_subs:
        result["hidden_subscribers"] = True
    return result


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 1 — resolve_channel
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def resolve_channel(identifier: str) -> str:
    """Resolve a YouTube @handle, custom URL, channel URL, or channel name
    into a full channel profile with stats.

    Accepts any of these formats:
      - @handle (e.g. "@allisonfromearth")
      - https://www.youtube.com/@handle
      - https://www.youtube.com/channel/UC... (direct channel ID URL)
      - A channel name to search for (e.g. "Allison From Earth")

    Returns:
        JSON with full channel details (same format as get_channel_details):
        channel_id, title, description, country, subscribers, total_views,
        video_count, topic_labels, keywords, channel_url.
    """
    if not YOUTUBE_API_KEY:
        return json.dumps({"error": "YOUTUBE_API_KEY not set."})

    identifier = identifier.strip()

    # Strategy 1: Direct channel ID
    channel_id = _extract_channel_id(identifier)
    if channel_id:
        return get_channel_details(channel_id)

    # Strategy 2: @handle (from URL or plain)
    handle = _extract_handle(identifier)
    if handle:
        data = _yt_get("channels", {
            "part": "snippet,statistics,topicDetails,brandingSettings",
            "forHandle": handle,
        })
        if "error" not in data and data.get("items"):
            return json.dumps(_build_channel_dict(data["items"][0]))

        # forHandle failed — fall through to search
        # (handle may be a legacy username or a display name)

    # Strategy 3: Try forUsername (for legacy youtube.com/user/... URLs)
    # Extract username from URL pattern or use as-is if short alphanumeric
    username = _extract_legacy_username(identifier)

    if username:
        data = _yt_get("channels", {
            "part": "snippet,statistics,topicDetails,brandingSettings",
            "forUsername": username,
        })
        if "error" not in data and data.get("items"):
            return json.dumps(_build_channel_dict(data["items"][0]))

    # Strategy 4: Search as a last resort
    # Clean the input — strip URL parts and @ if present
    search_term = _build_search_term(identifier, handle=handle)

    search_data = _yt_get("search", {
        "part": "snippet",
        "q": search_term,
        "type": "channel",
        "maxResults": 3,
    })

    if "error" in search_data:
        return json.dumps(search_data)

    items = search_data.get("items", [])
    if not items:
        return json.dumps({"error": f"Could not find a YouTube channel for '{identifier}'. "
                           "Try providing a channel ID (starts with UC) or a direct channel URL."})

    # Get the first result's channel ID and fetch full details
    first_channel_id = items[0].get("id", {}).get("channelId")
    if not first_channel_id:
        return json.dumps({"error": "Search returned results but no channel ID could be extracted."})

    return get_channel_details(first_channel_id)


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 2 — search_youtube_creators
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def search_youtube_creators(query: str, max_results: int = 6) -> str:
    """Search YouTube for creator channels matching a targeted brand query.

    Runs one query by default and merges results. Optional query expansion can
    be enabled with YOUTUBE_QUERY_VARIANTS=true.
    Filters: removes 0-sub, <1K sub, and 0-video channels.
    Sorted by subscriber count descending.

    Args:
        query: Focused search terms (e.g. "eco skincare sustainable beauty")
        max_results: Channels per variant (default 6, max 50)

    Returns:
        JSON with "channels" list: channel_id, title, description, country,
        subscribers, total_views, video_count, topic_labels, keywords, channel_url.
    """
    if not YOUTUBE_API_KEY:
        return json.dumps({"error": "YOUTUBE_API_KEY not set. Cannot search YouTube."})

    max_results = max(1, min(max_results, 50))
    queries = _expand_queries(query)
    seen_ids: set[str] = set()
    channel_ids: list[str] = []

    for q in queries:
        search_data = _yt_get("search", {
            "part": "snippet", "q": q, "type": "channel", "maxResults": max_results,
        })
        if "error" in search_data:
            continue
        for item in search_data.get("items", []):
            cid = item.get("id", {}).get("channelId")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                channel_ids.append(cid)

    if not channel_ids:
        return json.dumps({"channels": [], "queries_used": queries,
                           "message": "No channels found across all query variants."})

    stats_data = _yt_get("channels", {
        "part": "snippet,statistics,topicDetails,brandingSettings",
        "id": ",".join(channel_ids[:50]),
    })
    if "error" in stats_data:
        return json.dumps(stats_data)

    channels = []
    skipped = {"zero_subscribers": 0, "hidden_subscribers": 0, "below_min_subscribers": 0, "zero_videos": 0}

    for ch in stats_data.get("items", []):
        channel = _build_channel_dict(ch)
        subscribers = channel["subscribers"]
        video_count = channel["video_count"]

        if subscribers == -1:
            skipped["hidden_subscribers"] += 1; continue
        if subscribers <= 0:
            skipped["zero_subscribers"] += 1; continue
        if subscribers < MIN_SUBSCRIBERS:
            skipped["below_min_subscribers"] += 1; continue
        if video_count <= 0:
            skipped["zero_videos"] += 1; continue

        channels.append(channel)

    channels.sort(key=lambda c: c["subscribers"], reverse=True)
    return json.dumps({"channels": channels, "queries_used": queries,
                        "filters_applied": ["skip hidden subs", "skip subs<=0", f"skip subs<{MIN_SUBSCRIBERS}", "skip videos<=0"],
                        "skipped_counts": skipped})


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 3 — get_channel_details
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_channel_details(channel_id: str) -> str:
    """Get detailed statistics and metadata for a specific YouTube channel.

    Args:
        channel_id: YouTube channel ID (starts with UC)

    Returns:
        JSON with title, description, country, subscribers, total_views,
        video_count, topic_labels, keywords, channel_url.
    """
    if not YOUTUBE_API_KEY:
        return json.dumps({"error": "YOUTUBE_API_KEY not set."})

    data = _yt_get("channels", {
        "part": "snippet,statistics,topicDetails,brandingSettings",
        "id": channel_id,
    })
    if "error" in data:
        return json.dumps(data)

    items = data.get("items", [])
    if not items:
        return json.dumps({"error": f"Channel {channel_id} not found."})

    return json.dumps(_build_channel_dict(items[0]))


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 4 — get_channel_videos
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_channel_videos(channel_id: str, max_results: int = 5) -> str:
    """Get recent public videos (last 365 days) with engagement metrics.

    Pre-computes convenience fields:
      - avg_views_recent: average view count across returned videos
      - recent_video_titles: comma-separated video titles
      - recent_video_dates: comma-separated YYYY-MM-DD dates
      - engagement_rate_recent: (likes + comments) / views across recent videos

    Args:
        channel_id: YouTube channel ID
        max_results: Videos to fetch (default 5, max 20)

    Returns:
        JSON with videos list, avg_views_recent, recent_video_titles,
        recent_video_dates, recent_window_days.
    """
    if not YOUTUBE_API_KEY:
        return json.dumps({"error": "YOUTUBE_API_KEY not set."})

    max_results = max(1, min(max_results, 20))
    empty = {"videos": [], "avg_views_recent": 0, "recent_video_titles": "",
             "recent_video_dates": "", "recent_window_days": 365}

    search_data = _yt_get("search", {
        "part": "snippet", "channelId": channel_id, "type": "video",
        "order": "date", "publishedAfter": _recent_cutoff_iso(365),
        "maxResults": max_results,
    })
    if "error" in search_data:
        return json.dumps(search_data)

    items = search_data.get("items", [])
    if not items:
        return json.dumps({**empty, "message": "No recent videos found."})

    video_ids = [i["id"]["videoId"] for i in items if i.get("id", {}).get("videoId")]
    if not video_ids:
        return json.dumps({**empty, "message": "No video IDs found."})

    stats_data = _yt_get("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(video_ids)})
    if "error" in stats_data:
        return json.dumps(stats_data)

    videos = []
    shorts_count = 0
    for vid in stats_data.get("items", []):
        st = vid.get("statistics", {})
        sn = vid.get("snippet", {})
        # Detect Shorts: duration <= 60s in ISO 8601 format (PT#M#S / PT#S)
        duration_str = vid.get("contentDetails", {}).get("duration", "")
        is_short = _is_short_duration(duration_str)
        if is_short:
            shorts_count += 1
        videos.append({
            "video_id": vid["id"],
            "title": sn.get("title", ""),
            "published_at": sn.get("publishedAt", ""),
            "views": _safe_int(st.get("viewCount")),
            "likes": _safe_int(st.get("likeCount")),
            "comments": _safe_int(st.get("commentCount")),
            "is_short": is_short,
            "url": f"https://www.youtube.com/watch?v={vid['id']}",
        })

    videos.sort(key=lambda v: v.get("published_at", ""), reverse=True)

    avg = round(sum(v["views"] for v in videos) / len(videos)) if videos else 0
    total_likes = sum(v["likes"] for v in videos)
    total_comments = sum(v["comments"] for v in videos)
    total_views = sum(v["views"] for v in videos)
    titles = ", ".join(v["title"] for v in videos if v.get("title"))
    dates = ",".join(v["published_at"][:10] for v in videos
                     if v.get("published_at") and len(v["published_at"]) >= 10)

    shorts_ratio = round(shorts_count / len(videos), 2) if videos else 0.0

    return json.dumps({
        "videos": videos,
        "avg_views_recent": avg,
        "recent_video_titles": titles,
        "recent_video_dates": dates,
        "recent_window_days": 365,
        "total_likes_recent": total_likes,
        "total_comments_recent": total_comments,
        "total_views_recent": total_views,
        "engagement_rate_recent": (
            round((total_likes + total_comments) / total_views, 4)
            if total_views > 0 else 0.0
        ),
        "shorts_ratio": shorts_ratio,
        "shorts_count": shorts_count,
    })


@mcp.tool()
def cache_stats() -> str:
    """Return in-memory YouTube cache stats for quota observability."""
    total = _CACHE_HITS + _CACHE_MISSES
    hit_ratio = round(_CACHE_HITS / total, 3) if total else 0.0
    return json.dumps({
        "entries": len(_CACHE),
        "max_entries": _CACHE_MAX_ENTRIES,
        "hits": _CACHE_HITS,
        "misses": _CACHE_MISSES,
        "hit_ratio": hit_ratio,
    })


# ── entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
