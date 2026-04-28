"""
scoring.py — Deterministic Scoring Engine
──────────────────────────────────────────
Scores YouTube creators against brand briefs using a 100-point system.
All scoring is deterministic code — no LLM arithmetic involved.

Scoring breakdown (100 pts):
  25 pts — engagement rate ((likes + comments) / views, with view/subscriber fallback)
  25 pts — audience size (log scale, 1K–500K)
  20 pts — relevance (keyword overlap with synonym expansion)
  10 pts — geography (country / region match)
   5 pts — content activity (recent videos + posting frequency)
   5 pts — channel maturity (total video count)
   5 pts — recency (days since last post)
   5 pts — quality tiebreaker (fewer risk flags = higher score)

Also provides generate_media_kit for structured creator profiles.
"""

import math
import re
from datetime import datetime, timezone
from typing import List, Set

MIN_SUBSCRIBERS = 1000

# ══════════════════════════════════════════════════════════════════════════════
# KEYWORD & SYNONYM DATA
# ══════════════════════════════════════════════════════════════════════════════

_SHORT_DOMAIN_WORDS = {
    "eco", "bio", "gym", "fit", "men", "tea", "spa", "veg", "diy", "art",
    "gen", "b2b", "b2c", "usa", "sea", "apac", "asia", "uk", "eu", "us",
    "ai", "vr", "ar",
}

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "your", "their",
    "they", "them", "who", "what", "when", "where", "into", "about", "need",
    "looking", "find", "brand", "brands", "creator", "creators", "channel",
    "content", "audience", "target", "aged", "years", "year", "make", "makes",
    "video", "videos", "high", "good", "strong", "best", "new", "our",
}

_SYNONYM_CLUSTERS = {
    "skincare":     {"skincare", "skin-care", "skin", "complexion", "derma"},
    "beauty":       {"beauty", "cosmetics", "makeup", "make-up", "glam"},
    "clean":        {"clean", "organic", "natural", "non-toxic", "nontoxic", "chemical-free"},
    "sustainable":  {"sustainable", "sustainability", "green", "eco-friendly", "ecofriendly",
                     "zero-waste", "zerowaste", "ethical", "conscious"},
    "eco":          {"eco", "eco-friendly", "ecofriendly", "green", "sustainable"},
    "fitness":      {"fitness", "workout", "exercise", "training", "hiit", "crossfit"},
    "wellness":     {"wellness", "wellbeing", "well-being", "self-care", "selfcare",
                     "mindfulness", "holistic"},
    "tech":         {"tech", "technology", "gadget", "gadgets", "device", "devices"},
    "vegan":        {"vegan", "plant-based", "plantbased", "cruelty-free", "crueltyfree"},
    "travel":       {"travel", "traveling", "travelling", "backpacking", "nomad", "wanderlust"},
    "food":         {"food", "cooking", "recipe", "recipes", "culinary", "foodie", "chef"},
    "gaming":       {"gaming", "gamer", "esports", "gameplay", "streaming"},
    "fashion":      {"fashion", "style", "outfit", "outfits", "wardrobe", "apparel", "clothing"},
    "finance":      {"finance", "investing", "investment", "money", "budgeting"},
    "parenting":    {"parenting", "parent", "mom", "dad", "family", "motherhood", "fatherhood"},
    "productivity": {"productivity", "organization", "organisation", "planner", "time-management"},
    "supplement":   {"supplement", "supplements", "protein", "vitamins", "nutrition", "nutraceutical"},
    "lifestyle":    {"lifestyle", "daily-life", "routine", "vlog", "vlogs", "day-in-the-life"},
    "automotive":   {"automotive", "car", "cars", "vehicle", "vehicles", "auto", "driving", "motor",
                     "automobile", "truck", "suv"},
    "pets":         {"pets", "pet", "dog", "dogs", "cat", "cats", "animal", "animals", "puppy",
                     "kitten", "rescue", "adoption"},
    "music":        {"music", "musician", "song", "songs", "guitar", "piano", "singing", "singer",
                     "band", "album", "concert"},
    "comedy":       {"comedy", "funny", "humor", "humour", "sketch", "stand-up", "standup",
                     "comedian", "satire", "parody"},
    "motivation":   {"motivation", "motivational", "self-improvement", "mindset", "discipline",
                     "goals", "success", "hustle", "entrepreneurship"},
    "education":    {"education", "educational", "learning", "tutorial", "tutorials", "teach",
                     "teacher", "course", "lesson", "study"},
    "photography":  {"photography", "photo", "photos", "camera", "lens", "portrait", "landscape",
                     "lightroom", "editing"},
    "outdoor":      {"outdoor", "outdoors", "camping", "hiking", "backpacking", "adventure",
                     "trekking", "wilderness", "nature"},
}

_HIGH_SIGNAL_TERMS = {
    "skincare", "beauty", "clean", "vegan", "sustainable", "wellness", "fitness",
    "supplement", "gym", "workout", "travel", "lifestyle", "tech", "productivity",
    "software", "gadgets", "eco", "minimalism", "organization", "home", "gaming",
    "finance", "fashion", "food", "parenting", "education", "cooking", "recipe",
    "makeup", "haircare", "nutrition", "yoga", "meditation", "running", "cycling",
    "photography", "investing", "crypto", "automotive", "outdoors", "camping",
    "hiking", "gardening", "pets", "music", "comedy", "motivation",
    "cars", "dog", "cat", "humor", "mindset", "entrepreneur", "tutorial",
    "camera", "adventure", "wilderness", "singing", "guitar", "sketch",
    "vlog", "self-improvement", "plant-based", "zero-waste", "budgeting",
}

_PHRASE_BONUSES = [
    "clean beauty", "sustainable living", "zero waste", "eco friendly",
    "home organization", "travel vlog", "productivity software",
    "natural skincare", "vegan skincare", "workout supplement",
    "plant based", "self care", "personal finance", "home workout",
    "meal prep", "morning routine", "budget friendly", "cruelty free",
    "sensitive skin", "anti aging", "weight loss", "muscle building",
    "mental health", "side hustle",
    "car review", "car mod", "pet care", "dog training", "cat care",
    "stand up comedy", "sketch comedy", "self improvement", "daily motivation",
    "guitar tutorial", "music production", "outdoor adventure", "camping gear",
    "photo editing", "street photography", "family vlog", "mom life",
    "tech review", "software review", "coding tutorial", "game review",
]

# ══════════════════════════════════════════════════════════════════════════════
# GEOGRAPHY DATA
# ══════════════════════════════════════════════════════════════════════════════

_COUNTRY_ALIASES = {
    "united states": "us", "united states of america": "us", "usa": "us", "us": "us",
    "united kingdom": "gb", "uk": "gb", "great britain": "gb", "england": "gb",
    "singapore": "sg", "sg": "sg", "philippines": "ph", "ph": "ph",
    "indonesia": "id", "malaysia": "my", "thailand": "th", "vietnam": "vn",
    "australia": "au", "au": "au", "new zealand": "nz", "nz": "nz",
    "india": "in", "japan": "jp", "jp": "jp",
    "korea": "kr", "south korea": "kr", "kr": "kr", "taiwan": "tw", "tw": "tw",
    "hong kong": "hk", "hk": "hk", "germany": "de", "de": "de",
    "france": "fr", "fr": "fr", "spain": "es", "es": "es",
    "italy": "it", "netherlands": "nl", "nl": "nl",
    "canada": "ca", "ca": "ca", "brazil": "br", "br": "br",
    "mexico": "mx", "mx": "mx", "china": "cn", "cn": "cn",
}

_REGION_COUNTRY_MAP = {
    "southeast asia": {"sg", "ph", "id", "my", "th", "vn", "mm", "kh", "la", "bn"},
    "sea":            {"sg", "ph", "id", "my", "th", "vn", "mm", "kh", "la", "bn"},
    "apac":           {"sg", "ph", "id", "my", "th", "vn", "mm", "kh", "la", "bn",
                       "au", "nz", "jp", "kr", "cn", "tw", "hk", "in", "pk"},
    "asia":           {"sg", "ph", "id", "my", "th", "vn", "mm", "kh", "la", "bn",
                       "jp", "kr", "cn", "tw", "hk", "in", "pk"},
    "latin america":  {"br", "mx", "ar", "cl", "co", "pe"},
    "latam":          {"br", "mx", "ar", "cl", "co", "pe"},
    "middle east":    {"ae", "sa", "qa", "kw", "bh", "om", "il", "jo", "lb"},
    "europe":         {"gb", "de", "fr", "es", "it", "nl", "se", "no", "dk", "fi",
                       "pl", "pt", "be", "at", "ch"},
    "global": None, "worldwide": None,
}


# ══════════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _parse_int(val, default: int = 0) -> int:
    """Safely parse integers that Gemini may pass as strings like '380K'."""
    if isinstance(val, int):
        return val
    try:
        s = str(val).upper().replace(",", "").strip()
        if "M" in s:
            return int(float(s.replace("M", "")) * 1_000_000)
        if "K" in s:
            return int(float(s.replace("K", "")) * 1_000)
        return int(float(s))
    except (ValueError, TypeError):
        return default


def _tokenise(text: str) -> Set[str]:
    """Tokenize text for heuristic overlap scoring."""
    if not text:
        return set()
    raw_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-+/&']*", text.lower())
    tokens: Set[str] = set()
    for token in raw_tokens:
        token = token.strip("-+/&'")
        if not token or token in _STOPWORDS:
            continue
        if len(token) >= 4 or token in _SHORT_DOMAIN_WORDS:
            tokens.add(token)
    return tokens


def _expand_synonyms(tokens: Set[str]) -> Set[str]:
    """Expand a token set with synonyms from _SYNONYM_CLUSTERS."""
    expanded = set(tokens)
    for _canonical, cluster in _SYNONYM_CLUSTERS.items():
        if tokens & cluster:
            expanded |= cluster
    return expanded


def _normalise_country(country: str) -> str:
    """Normalize country values to short country codes."""
    cleaned = (country or "").strip().lower()
    return _COUNTRY_ALIASES.get(cleaned, cleaned) if cleaned else ""


def _keyword_overlap(brand_brief: str, creator_text: str) -> int:
    """Heuristic keyword-overlap score with synonym expansion and phrase bonuses."""
    brand_tokens = _expand_synonyms(_tokenise(brand_brief))
    creator_tokens = _expand_synonyms(_tokenise(creator_text))
    overlap = brand_tokens.intersection(creator_tokens)

    score = len(overlap) + len(overlap.intersection(_HIGH_SIGNAL_TERMS))

    brand_lower = (brand_brief or "").lower()
    creator_lower = (creator_text or "").lower()
    for phrase in _PHRASE_BONUSES:
        if phrase in brand_lower and phrase in creator_lower:
            score += 2

    return score


def _geo_score(brand_brief: str, country: str) -> float:
    """Compute geography match score (0–10).

    Uses country code normalization and region maps. Short codes (us, uk, sg)
    are matched as whole words via regex to prevent substring collisions
    (e.g. 'in' for India vs the English word 'in').
    """
    country_norm = _normalise_country(country)
    if not country_norm or country_norm == "unknown":
        return 0.0

    brief_lower = (brand_brief or "").lower()

    for alias, code in _COUNTRY_ALIASES.items():
        if code != country_norm:
            continue
        if len(alias) >= 4:
            if alias in brief_lower:
                return 10.0
        else:
            if re.search(r'\b' + re.escape(alias) + r'\b', brief_lower):
                if alias in ("in", "it"):
                    continue
                return 10.0

    for region_kw, country_set in _REGION_COUNTRY_MAP.items():
        if region_kw in brief_lower:
            if country_set is None:
                return 5.0
            if country_norm in country_set:
                return 7.0

    return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC TOOLS — called by the root agent
# ══════════════════════════════════════════════════════════════════════════════

def score_creator_fit(
    brand_brief: str,
    creator_name: str,
    subscribers: int = 0,
    avg_views: int = 0,
    content_topics: str = "",
    country: str = "Unknown",
    channel_description: str = "",
    recent_video_titles: str = "",
    video_count: int = 0,
    recent_video_dates: str = "",
    shorts_ratio: float = 0.0,
    total_comments_recent: int = 0,
    total_likes_recent: int = 0,
    total_views_recent: int = 0,
) -> dict:
    """Deterministic scoring of a creator against a brand brief (100 pts max).

    Scoring breakdown:
      25 pts — engagement rate ((likes + comments) / views, with view/subscriber fallback)
      25 pts — audience size (log scale, 1K–500K)
      20 pts — relevance (topics + description + video titles vs brief, with synonyms)
      10 pts — geography match (country / region / global)
       5 pts — content activity (recent videos + posting frequency from dates)
       5 pts — channel maturity (total video count)
       5 pts — recency (days since last post)
       5 pts — quality tiebreaker (fewer risk flags = higher score)

    All scoring is deterministic code — no LLM arithmetic involved.

    Args:
        brand_brief: The brand's campaign description and target audience
        creator_name: Name of the YouTube creator
        subscribers: Channel subscriber count
        avg_views: Average views per recent video
        content_topics: Comma-separated content topics
        country: Creator's country
        channel_description: Full channel description — IMPORTANT for relevance scoring
        recent_video_titles: Comma-separated recent video titles — IMPORTANT for relevance + activity
        video_count: Total videos on channel — IMPORTANT for maturity scoring
        recent_video_dates: Comma-separated ISO dates e.g. "2026-03-01,2026-02-15"
        shorts_ratio: Fraction of recent videos that are Shorts (0.0–1.0), from get_channel_videos
        total_comments_recent: Sum of comments across recent videos, from get_channel_videos
        total_likes_recent: Sum of likes across recent videos, from get_channel_videos
        total_views_recent: Sum of views across recent videos, from get_channel_videos

    Returns:
        dict with fit_score (0-100), engagement_rate, engagement_rating,
        risk_flags, confidence, and reasoning.
    """
    subscribers = _parse_int(subscribers)
    avg_views = _parse_int(avg_views)
    video_count = _parse_int(video_count)
    total_comments_recent = _parse_int(total_comments_recent)
    total_likes_recent = _parse_int(total_likes_recent)
    total_views_recent = _parse_int(total_views_recent)
    try:
        shorts_ratio = float(shorts_ratio)
    except (TypeError, ValueError):
        shorts_ratio = 0.0

    if subscribers < MIN_SUBSCRIBERS:
        return {
            "creator_name": creator_name,
            "fit_score": 0,
            "engagement_rate": "N/A",
            "engagement_source": "not_scored",
            "engagement_formula": "N/A",
            "engagement_rating": "Too Small",
            "subscribers": subscribers,
            "country": country or "Unknown",
            "risk_flags": [f"Below minimum subscriber threshold ({MIN_SUBSCRIBERS:,})."],
            "confidence": "low",
            "reasoning": f"{creator_name} has only {subscribers:,} subscribers, "
                         f"below the {MIN_SUBSCRIBERS:,} minimum for shortlisting.",
        }

    # ── Engagement (25 pts) ────────────────────────────────────────────────
    # Prefer true interaction engagement when recent video totals are present:
    # (likes + comments) / views. Fall back to avg_views / subscribers for
    # older call sites or channels where like/comment counts are unavailable.
    interaction_count = total_likes_recent + total_comments_recent
    if total_views_recent > 0 and interaction_count > 0:
        eng_rate = min(interaction_count / total_views_recent, 1.0)
        engagement_source = "likes_comments_per_view"
        engagement_formula = (
            f"({total_likes_recent:,} likes + {total_comments_recent:,} comments) "
            f"/ {total_views_recent:,} views"
        )
        engagement_pts = min(eng_rate / 0.06, 1.0) * 25
        if eng_rate >= 0.04:      eng_label = "High"
        elif eng_rate >= 0.015:   eng_label = "Average"
        else:                     eng_label = "Low"
    else:
        eng_rate = min(avg_views / subscribers, 1.0) if subscribers > 0 else 0.0
        engagement_source = "views_per_subscriber_fallback"
        engagement_formula = f"{avg_views:,} avg views / {subscribers:,} subscribers"
        engagement_pts = min(eng_rate / 0.10, 1.0) * 25
        if eng_rate >= 0.05:      eng_label = "High"
        elif eng_rate >= 0.02:    eng_label = "Average"
        else:                     eng_label = "Low"

    # ── Audience (25 pts, log scale) ───────────────────────────────────────
    log_subs = math.log10(max(subscribers, MIN_SUBSCRIBERS))
    log_min = math.log10(MIN_SUBSCRIBERS)
    log_max = math.log10(500_000)
    audience_pts = min(max((log_subs - log_min) / (log_max - log_min), 0.0), 1.0) * 25

    # ── Relevance (20 pts, synonym-expanded keyword overlap) ───────────────
    creator_text = " ".join([
        content_topics or "",
        channel_description[:1_000] if channel_description else "",
        recent_video_titles or "",
    ])
    overlap_score = _keyword_overlap(brand_brief, creator_text)
    relevance_pts = min(overlap_score, 10) / 10 * 20

    # ── Geography (10 pts) ─────────────────────────────────────────────────
    geo_pts = _geo_score(brand_brief, country)

    # ── Activity (5 pts) ───────────────────────────────────────────────────
    video_titles = [t.strip() for t in recent_video_titles.split(",") if t.strip()]
    sample_pts = min(len(video_titles), 4) / 4 * 2

    freq_pts = 0.0
    parsed_dates = []
    if recent_video_dates and recent_video_dates.strip():
        for ds in [d.strip()[:10] for d in recent_video_dates.split(",") if d.strip()]:
            try:
                parsed_dates.append(datetime.strptime(ds, "%Y-%m-%d").date())
            except ValueError:
                continue

    if len(parsed_dates) >= 2:
        sorted_dates = sorted(parsed_dates)
        span_days = max((sorted_dates[-1] - sorted_dates[0]).days, 1)
        posts_per_month = len(sorted_dates) / span_days * 30
        if posts_per_month >= 8:      freq_pts = 3.0
        elif posts_per_month >= 4:    freq_pts = 2.5
        elif posts_per_month >= 2:    freq_pts = 2.0
        elif posts_per_month >= 1:    freq_pts = 1.0
        else:                         freq_pts = 0.5
    elif video_count >= 100:          freq_pts = 2.0
    elif video_count >= 50:           freq_pts = 1.5
    elif video_count >= 20:           freq_pts = 1.0
    elif video_count >= 5:            freq_pts = 0.5

    activity_pts = sample_pts + freq_pts

    # ── Maturity (5 pts) ───────────────────────────────────────────────────
    if video_count >= 200:    maturity_pts = 5.0
    elif video_count >= 100:  maturity_pts = 3.5
    elif video_count >= 50:   maturity_pts = 2.0
    elif video_count >= 20:   maturity_pts = 1.0
    else:                     maturity_pts = 0.0

    # ── Recency (5 pts) ───────────────────────────────────────────────────
    recency_pts = 0.0
    days_since_last = None
    if parsed_dates:
        days_since_last = (datetime.now(timezone.utc).date() - max(parsed_dates)).days
        if days_since_last <= 30:     recency_pts = 5.0
        elif days_since_last <= 60:   recency_pts = 4.0
        elif days_since_last <= 90:   recency_pts = 3.0
        elif days_since_last <= 120:  recency_pts = 2.0
        elif days_since_last <= 180:  recency_pts = 1.0

    # ── Risk flags ─────────────────────────────────────────────────────────
    risk_flags: List[str] = []
    country_norm = _normalise_country(country)

    if eng_label == "Low":
        if engagement_source == "likes_comments_per_view":
            risk_flags.append("Low recent like/comment engagement per view.")
        else:
            risk_flags.append("Low recent view-to-subscriber ratio.")
    if eng_rate > 0.80:
        risk_flags.append("Unusually high engagement — may indicate viral outlier, Shorts-heavy channel, or incomplete view data.")
    if overlap_score < 2:
        risk_flags.append("Weak topical overlap with the brand brief.")
    if not content_topics.strip():
        risk_flags.append("Missing clear topic metadata.")
    if not video_titles:
        risk_flags.append("No recent video sample available.")
    if not country_norm or country_norm == "unknown":
        risk_flags.append("Creator geography unknown.")
    if 0 < video_count < 10:
        risk_flags.append("Very few total videos — channel may be new.")
    if subscribers > 100_000 and engagement_source == "views_per_subscriber_fallback" and eng_rate < 0.01:
        risk_flags.append("Large audience but very low engagement — possible inactive subscribers.")
    if days_since_last is not None and days_since_last > 90:
        risk_flags.append(f"No posts in {days_since_last} days — channel may be inactive.")
    if shorts_ratio >= 0.8 and len(video_titles) >= 3:
        risk_flags.append(f"Shorts-heavy channel ({shorts_ratio:.0%} Shorts) — may not suit long-form brand integrations.")
    elif shorts_ratio >= 0.5 and len(video_titles) >= 3:
        risk_flags.append(f"Mixed content ({shorts_ratio:.0%} Shorts) — confirm brand is open to short-form placements.")

    comment_view_ratio = 0.0
    if total_views_recent > 0 and total_comments_recent > 0:
        comment_view_ratio = total_comments_recent / total_views_recent
        if comment_view_ratio < 0.001 and total_views_recent > 50_000:
            risk_flags.append("Very low comment-to-view ratio — audience may not be highly engaged.")

    # ── Quality tiebreaker (5 pts) ─────────────────────────────────────────
    quality_pts = max(5.0 - len(risk_flags), 0.0)

    # ── Total ──────────────────────────────────────────────────────────────
    total = round(
        engagement_pts + audience_pts + relevance_pts + geo_pts
        + activity_pts + maturity_pts + recency_pts + quality_pts,
        1,
    )
    total = min(total, 100.0)

    # ── Confidence ─────────────────────────────────────────────────────────
    signals = sum(1 for c in [
        subscribers >= MIN_SUBSCRIBERS, avg_views > 0, content_topics.strip(),
        channel_description.strip() if channel_description else False,
        video_titles,
        country_norm and country_norm != "unknown",
        video_count > 0,
        bool(parsed_dates),
    ] if c)
    confidence = "high" if signals >= 6 else ("medium" if signals >= 4 else "low")

    # ── Reasoning ──────────────────────────────────────────────────────────
    bits = [f"{creator_name}: {subscribers:,} subs, {eng_label.lower()} engagement ({eng_rate:.1%})"]
    if engagement_source == "likes_comments_per_view":
        bits.append(f"engagement formula: {engagement_formula}")
    if avg_views > 0:
        bits.append(f"avg {avg_views:,} views/video")
    if content_topics.strip():
        bits.append(f"topics: {content_topics}")
    if country and str(country).strip().lower() != "unknown":
        bits.append(f"country: {country}")
    if overlap_score >= 6:
        bits.append("strong topical alignment with brand brief")
    elif overlap_score >= 3:
        bits.append("moderate topical alignment with brand brief")
    elif overlap_score >= 1:
        bits.append("limited topical alignment with brand brief")
    else:
        bits.append("no detectable topical alignment with brand brief")
    if video_count >= 50:
        bits.append(f"established channel ({video_count} videos)")
    if days_since_last is not None:
        if days_since_last <= 30:
            bits.append("active (posted within 30 days)")
        elif days_since_last <= 90:
            bits.append(f"last posted {days_since_last} days ago")
        else:
            bits.append(f"inactive ({days_since_last} days since last post)")
    if shorts_ratio >= 0.5:
        bits.append(f"Shorts-heavy ({shorts_ratio:.0%})")
    if comment_view_ratio >= 0.02:
        bits.append("strong comment engagement")

    # ── Score components (for UI transparency) ─────────────────────────────
    score_components = [
        {"key": "engagement", "label": "Engagement",   "points": round(engagement_pts, 1), "max": 25},
        {"key": "audience",   "label": "Audience",     "points": round(audience_pts, 1),   "max": 25},
        {"key": "relevance",  "label": "Relevance",    "points": round(relevance_pts, 1),  "max": 20},
        {"key": "geography",  "label": "Geography",    "points": round(geo_pts, 1),        "max": 10},
        {"key": "activity",   "label": "Activity",     "points": round(activity_pts, 1),   "max": 5},
        {"key": "maturity",   "label": "Maturity",     "points": round(maturity_pts, 1),   "max": 5},
        {"key": "recency",    "label": "Recency",      "points": round(recency_pts, 1),    "max": 5},
        {"key": "quality",    "label": "Quality",      "points": round(quality_pts, 1),    "max": 5},
    ]

    return {
        "creator_name": creator_name,
        "fit_score": total,
        "engagement_rate": f"{eng_rate:.1%}",
        "engagement_source": engagement_source,
        "engagement_formula": engagement_formula,
        "total_likes_recent": total_likes_recent,
        "total_comments_recent": total_comments_recent,
        "total_views_recent": total_views_recent,
        "engagement_rating": eng_label,
        "subscribers": subscribers,
        "avg_views_per_video": avg_views,
        "country": country or "Unknown",
        "risk_flags": risk_flags,
        "confidence": confidence,
        "reasoning": "; ".join(bits) + ".",
        "score_components": score_components,
    }


def generate_media_kit(
    creator_name: str,
    channel_id: str,
    subscribers: int,
    total_views: int,
    avg_views: int,
    top_topics: str,
    country: str,
    recent_video_titles: str,
    video_count: int = 0,
    engagement_rate: str = "",
) -> dict:
    """Generate a structured media kit for the top creator match.

    Args:
        creator_name: Channel name
        channel_id: YouTube channel ID
        subscribers: Subscriber count
        total_views: Lifetime total views
        avg_views: Average views on recent videos
        top_topics: Comma-separated content topics
        country: Creator's country
        recent_video_titles: Comma-separated recent video titles
        video_count: Total videos on the channel
        engagement_rate: Formatted engagement rate string e.g. "5.2%"
    """
    topics = [t.strip() for t in top_topics.split(",") if t.strip()]
    highlights = [t.strip() for t in recent_video_titles.split(",") if t.strip()][:5]
    kit = {
        "creator_name": creator_name,
        "channel_url": f"https://www.youtube.com/channel/{channel_id}",
        "subscribers": subscribers,
        "total_views": total_views,
        "avg_views_per_video": avg_views,
        "top_content_topics": topics,
        "country": country or "Unknown",
        "recent_highlights": highlights,
        "collaboration_formats": [
            "Dedicated sponsor video",
            "Product integration / mention",
            "Giveaway or contest",
            "Brand ambassador (long-term)",
        ],
    }
    if video_count > 0:
        kit["total_videos"] = video_count
    if engagement_rate:
        kit["engagement_rate"] = engagement_rate
    return kit
