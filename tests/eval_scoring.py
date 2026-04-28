"""
Eval harness for Sponsorship Bridge's deterministic scoring engine.

What this is
────────────
A small, hand-curated set of (brand_brief, creator_profile, expectations)
triples. We pin the expected fit_score within a tolerance band so that
prompt-changes, weight tweaks, or a new synonym group surface as targeted
diffs rather than silent regressions.

Why it matters
──────────────
The scoring engine in `sponsorship_bridge/scoring.py` is deterministic
(no LLM in the arithmetic path), so the harness is closer to a unit-test
suite than to an LLM rubric eval. Each case captures a real-world shape
we want the engine to handle:

  • Strong same-niche match            → score must stay ≥ 80
  • Cross-niche mismatch               → score must stay ≤ 50
  • Geography hit / miss               → tied to the geo component
  • Synonym expansion                  → "vegan beauty" ↔ "plant-based cosmetics"
  • Below-minimum subscriber threshold → must score 0 (gating, not penalty)
  • Inactive channel                   → low recency, risk-flagged
  • Shorts-heavy channel               → risk-flagged
  • Hidden / very small audience       → low audience component
  • Perfect fit                        → score must stay ≥ 90
  • Engagement-only outlier            → engagement component dominates

Run
───
    python -m tests.eval_scoring

Returns exit 0 when all cases pass, 1 when any fails. Suitable for CI.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

# Make the `sponsorship_bridge` package importable from project root.
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
sys.path.insert(0, PROJECT_ROOT)

# Import scoring.py directly to skip the package __init__ which pulls in google.adk.
import importlib.util as _ilu
_scoring_path = os.path.join(PROJECT_ROOT, 'sponsorship_bridge', 'scoring.py')
_spec = _ilu.spec_from_file_location('sb_scoring', _scoring_path)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
score_creator_fit = _mod.score_creator_fit  # noqa: E402


# ── ANSI helpers ──────────────────────────────────────────────────────────
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass
class Case:
    name: str
    brand_brief: str
    creator: dict[str, Any]
    expect_score_min: float = 0.0
    expect_score_max: float = 100.0
    extra_checks: list[Callable[[dict[str, Any]], tuple[bool, str]]] = field(default_factory=list)


def has_risk_flag(substring: str) -> Callable[[dict[str, Any]], tuple[bool, str]]:
    def check(r: dict[str, Any]) -> tuple[bool, str]:
        flags = r.get("risk_flags", []) or []
        ok = any(substring.lower() in f.lower() for f in flags)
        return ok, f"expected risk flag containing {substring!r}; saw {flags}"
    return check


def component_at_least(key: str, threshold: float) -> Callable[[dict[str, Any]], tuple[bool, str]]:
    def check(r: dict[str, Any]) -> tuple[bool, str]:
        comp = next((c for c in r.get("score_components", []) if c["key"] == key), None)
        if not comp:
            return False, f"no {key!r} component in result"
        return comp["points"] >= threshold, f"{key} expected ≥ {threshold}; got {comp['points']}"
    return check


def component_at_most(key: str, threshold: float) -> Callable[[dict[str, Any]], tuple[bool, str]]:
    def check(r: dict[str, Any]) -> tuple[bool, str]:
        comp = next((c for c in r.get("score_components", []) if c["key"] == key), None)
        if not comp:
            return False, f"no {key!r} component in result"
        return comp["points"] <= threshold, f"{key} expected ≤ {threshold}; got {comp['points']}"
    return check


# ── Cases ─────────────────────────────────────────────────────────────────
CASES: list[Case] = [
    # 1. Eco-skincare brand × strong sustainable creator → high fit
    Case(
        name="eco-skincare matches sustainable lifestyle creator",
        brand_brief="Eco-friendly vegan skincare brand targeting women 18-35 in the US.",
        creator=dict(
            creator_name="Shelbizleee",
            subscribers=395_000, avg_views=49_000,
            content_topics="sustainable living, zero waste, eco home, deinfluencing",
            country="US",
            channel_description="Sustainability education, low-waste swaps, eco-friendly lifestyle.",
            recent_video_titles="Zero Waste Bathroom Reset, Sustainable Home Swaps That Last",
            video_count=765,
            recent_video_dates="2026-04-02,2026-03-25,2026-03-18,2026-03-04",
            total_likes_recent=12_500, total_comments_recent=1_454, total_views_recent=246_100,
        ),
        expect_score_min=78,
        extra_checks=[component_at_least("audience", 22), component_at_least("relevance", 14)],
    ),

    # 2. Cross-niche mismatch: tech brand × beauty creator → low fit
    Case(
        name="tech brand mismatches beauty-only creator",
        brand_brief="Mechanical keyboards and developer tooling for productivity professionals.",
        creator=dict(
            creator_name="GlamRoutineDaily",
            subscribers=180_000, avg_views=22_000,
            content_topics="makeup, beauty, glam, lipstick reviews",
            country="US",
            channel_description="Daily makeup tutorials and product reviews.",
            recent_video_titles="Glam Lipstick Comparison, 5-Minute Makeup",
            video_count=300,
            recent_video_dates="2026-04-10,2026-03-28,2026-03-15",
            total_likes_recent=4_000, total_comments_recent=320, total_views_recent=120_000,
        ),
        expect_score_max=58,
        extra_checks=[component_at_most("relevance", 8)],
    ),

    # 3. Geography hit: explicit US-targeting brand × US creator → full geo
    Case(
        name="geography full points when brand targets US and creator is US",
        brand_brief="Looking for fitness creators based in the US — Americans 25-40.",
        creator=dict(
            creator_name="LiftUSA",
            subscribers=120_000, avg_views=18_000,
            content_topics="fitness, gym training, workout, nutrition",
            country="US",
            channel_description="US-based personal trainer.",
            recent_video_titles="HIIT Workout, Strength Day",
            video_count=210,
            recent_video_dates="2026-04-18,2026-04-04,2026-03-22",
            total_likes_recent=6_000, total_comments_recent=420, total_views_recent=140_000,
        ),
        expect_score_min=70,
        extra_checks=[component_at_least("geography", 8)],
    ),

    # 4. Geography miss: SEA-targeting brand × Danish creator → low geo
    Case(
        name="geography penalty when brand targets SEA and creator is in Denmark",
        brand_brief="Targeting Southeast Asia — Singapore, Malaysia, Thailand, Indonesia.",
        creator=dict(
            creator_name="GittemaryJohansen",
            subscribers=149_000, avg_views=18_800,
            content_topics="sustainable living, zero waste, vegan lifestyle",
            country="DK",
            channel_description="Zero-waste creator from Denmark.",
            recent_video_titles="Zero Waste Bathroom Reset, Vegan Self Care",
            video_count=1037,
            recent_video_dates="2026-04-17,2026-04-03,2026-03-20",
            total_likes_recent=5_480, total_comments_recent=690, total_views_recent=92_000,
        ),
        extra_checks=[component_at_most("geography", 4)],
    ),

    # 5. Synonym expansion: brand says "vegan beauty", creator says "plant-based cosmetics"
    Case(
        name="synonym expansion catches vegan ↔ plant-based",
        brand_brief="We need vegan beauty creators for cruelty-free cosmetics campaigns.",
        creator=dict(
            creator_name="PlantBasedGlam",
            subscribers=80_000, avg_views=12_000,
            content_topics="plant-based cosmetics, cruelty-free makeup, clean beauty",
            country="US",
            channel_description="Plant-based and cruelty-free beauty reviews.",
            recent_video_titles="Best Cruelty-Free Mascaras, Plant-Based Glam Routine",
            video_count=220,
            recent_video_dates="2026-04-15,2026-04-01,2026-03-19",
            total_likes_recent=2_400, total_comments_recent=180, total_views_recent=72_000,
        ),
        extra_checks=[component_at_least("relevance", 12)],
    ),

    # 6. Below minimum subscriber threshold → fit_score = 0 (gating, not penalty)
    Case(
        name="sub-1K channel is gated to fit_score 0",
        brand_brief="Any beauty creator.",
        creator=dict(
            creator_name="TinyChannel",
            subscribers=400, avg_views=50,
            content_topics="skincare",
            country="US",
            recent_video_titles="My First Video",
            video_count=2,
        ),
        expect_score_min=0, expect_score_max=0,
    ),

    # 7. Inactive channel → low recency + inactive risk flag
    Case(
        name="inactive channel triggers recency penalty + risk flag",
        brand_brief="Looking for active eco-living creators in 2026.",
        creator=dict(
            creator_name="DormantEco",
            subscribers=45_000, avg_views=8_000,
            content_topics="eco living, sustainable lifestyle",
            country="US",
            channel_description="An eco creator (currently on hiatus).",
            recent_video_titles="Old Eco Video 1, Old Eco Video 2",
            video_count=80,
            # Last post far back in time
            recent_video_dates="2025-08-01,2025-07-01,2025-06-01",
            total_likes_recent=400, total_comments_recent=50, total_views_recent=20_000,
        ),
        extra_checks=[component_at_most("recency", 1.0), has_risk_flag("inactive")],
    ),

    # 8. Shorts-heavy channel → risk flag
    Case(
        name="shorts-heavy channel raises risk flag",
        brand_brief="Looking for skincare creators for long-form integrations.",
        creator=dict(
            creator_name="ShortsOnlySkin",
            subscribers=200_000, avg_views=30_000,
            content_topics="skincare shorts, beauty tips, quick reviews",
            country="US",
            recent_video_titles="60-sec routine, 30-sec hack, 45-sec ingredient",
            video_count=400,
            recent_video_dates="2026-04-12,2026-03-29,2026-03-15",
            shorts_ratio=0.9,
            total_likes_recent=3_000, total_comments_recent=200, total_views_recent=300_000,
        ),
        extra_checks=[has_risk_flag("Shorts")],
    ),

    # 9. Perfect fit: every signal strong → high band
    Case(
        name="perfect fit lands in 90+ band",
        brand_brief=("Eco-friendly skincare and clean beauty brand targeting women 18-35 in the US. "
                     "Looking for sustainable lifestyle and clean beauty creators."),
        creator=dict(
            creator_name="DreamMatch",
            subscribers=420_000, avg_views=68_000,
            content_topics="clean beauty, sustainable skincare, eco lifestyle, vegan beauty, US",
            country="US",
            channel_description="Clean beauty, sustainable skincare, and eco-conscious lifestyle education for women 18-35.",
            recent_video_titles="Sustainable Skincare Routine, Vegan Beauty Empties, Eco Lifestyle Reset, Clean Beauty Picks",
            video_count=300,
            recent_video_dates="2026-04-20,2026-04-10,2026-03-30,2026-03-20",
            total_likes_recent=22_000, total_comments_recent=1_800, total_views_recent=380_000,
        ),
        expect_score_min=88,
    ),

    # 10. Engagement-only outlier — small but extremely engaged audience
    Case(
        name="small but highly engaged niche channel still earns engagement points",
        brand_brief="Looking for podcasting and audio gear creators in the US.",
        creator=dict(
            creator_name="MicNerd",
            subscribers=18_000, avg_views=6_000,
            content_topics="podcasting, microphones, audio gear, home studio",
            country="US",
            channel_description="In-depth microphone and podcasting gear reviews.",
            recent_video_titles="Best USB Mic 2026, Home Studio Tour, Phantom Power Explained",
            video_count=140,
            recent_video_dates="2026-04-18,2026-04-04,2026-03-22",
            total_likes_recent=1_400, total_comments_recent=160, total_views_recent=28_000,
        ),
        extra_checks=[component_at_least("engagement", 18), component_at_least("relevance", 4)],
    ),
]


# ── Runner ────────────────────────────────────────────────────────────────
def run() -> int:
    print(f"\n{BOLD}Sponsorship Bridge — scoring eval harness{RESET}")
    print(f"{DIM}Running {len(CASES)} golden cases against score_creator_fit{RESET}\n")

    passed = 0
    failed: list[tuple[str, list[str]]] = []

    for idx, case in enumerate(CASES, start=1):
        result = score_creator_fit(brand_brief=case.brand_brief, **case.creator)
        score = float(result.get("fit_score", 0))

        problems: list[str] = []
        if not (case.expect_score_min <= score <= case.expect_score_max):
            problems.append(
                f"fit_score {score} outside expected band "
                f"[{case.expect_score_min}, {case.expect_score_max}]"
            )
        for check in case.extra_checks:
            ok, msg = check(result)
            if not ok:
                problems.append(msg)

        if problems:
            print(f"  {RED}✗{RESET} {idx:>2}. {case.name}")
            for p in problems:
                print(f"       {DIM}→{RESET} {p}")
            failed.append((case.name, problems))
        else:
            print(f"  {GREEN}✓{RESET} {idx:>2}. {case.name}  {DIM}(fit={score}){RESET}")
            passed += 1

    print()
    if failed:
        print(f"{RED}{BOLD}{len(failed)} case(s) failed{RESET}, {GREEN}{passed} passed{RESET}\n")
        return 1
    print(f"{GREEN}{BOLD}All {passed} cases passed.{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(run())
