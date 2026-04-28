# Sponsorship Bridge

> A multi-agent AI system that matches **YouTube creators with brand sponsors** — discovers, scores, drafts the outreach, and books the intro call. Built on **Google ADK + Gemini 2.5 Flash + MCP**, deployed on **Cloud Run**.

Built for **Gen AI Academy APAC 2026 — Cohort 1 Hackathon**.

---

## What it does

Sponsorship Bridge is a **two-sided matching workflow** for brand-creator sponsorships:

- **For brands** — describe a campaign, get a ranked top-three of YouTube creators with deterministic 8-signal fit scores, a media kit for the top match, an AI-drafted outreach DM, and a calendar booking flow.
- **For creators** — describe your channel, get the top brand campaigns from the database with pitch angles, an outreach pitch from your voice to the brand, and the same booking flow.

The whole loop — discover, score, match, draft outreach, schedule — runs in one agent turn, with a refinement loop that lets users iterate on the brief mid-flow.

---

## Why this is built this way

The hackathon brief asks for a multi-agent AI system that helps users manage tasks, schedules, and information across multiple tools and data sources. Sponsorship Bridge addresses each pillar:

| Requirement | Implementation |
|---|---|
| Primary agent + sub-agents | `root_agent` (orchestrator) + `analytics_agent` (database) + `scheduling_agent` (calendar). All Google ADK. |
| Structured data store | SQLite — 10 brand campaigns with brand-voice descriptions; persists match results and history. |
| Multi-tool MCP integration | Two stdio MCP servers: YouTube Data API v3 (4 tools) + Google Calendar API (3 tools). |
| Multi-step workflows | Brand Mode runs Search → Score → Tie-break → Media Kit → Save → Outreach Draft → Schedule in one turn. |
| API-based deployment | Cloud Run via Docker, single `deploy.sh` script. Vertex AI for the model. |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     Sponsorship Bridge (Root Agent)                          │
│                     Gemini 2.5 Flash via Vertex AI                           │
│                                                                              │
│   Owns: YouTube MCP tools, score_creator_fit, generate_media_kit,            │
│         save_match_result. Runs full Brand Mode flow inline.                 │
└────────────────┬────────────────────────────────────┬────────────────────────┘
                 │                                    │
          ┌──────▼───────┐                    ┌───────▼────────┐
          │  Analytics   │                    │   Scheduling   │
          │   Agent      │                    │    Agent       │
          │              │                    │                │
          │ get_active_  │                    │ Calendar MCP   │
          │ brand_       │                    │ tools          │
          │ campaigns,   │                    │                │
          │ get_match_   │                    │                │
          │ history      │                    │                │
          └──────────────┘                    └───────┬────────┘
                                                      │
      ┌────────────────────────┐         ┌────────────▼──────────────┐
      │    YouTube MCP Server  │         │    Calendar MCP Server    │
      │  • search_creators     │         │  • check_availability     │
      │  • get_channel_details │         │  • create_meeting         │
      │  • get_channel_videos  │         │  • list_upcoming_events   │
      │  • resolve_channel     │         │  (stub + real OAuth)      │
      └────────────┬───────────┘         └────────────┬──────────────┘
                   │                                  │
          YouTube Data API v3                Google Calendar API

  Outreach drafter (Vertex Gemini, single-call) sits alongside the agents
  and produces personalized DMs in either brand→creator or creator→brand voice.
```

### Key design decisions

**Root agent owns the full Brand Mode flow.** In ADK 1.x, sub-agent responses surface directly to users. To control presentation, the root agent runs YouTube discovery + scoring + tie-breaks inline and only delegates to sub-agents for purely-mechanical work (DB reads, calendar booking).

**Deterministic scoring, transparent UI.** All 100 points are computed in code across 8 weighted signals (engagement 25, audience 25, relevance 20, geography 10, activity 5, maturity 5, recency 5, quality 5). The UI exposes every component on a *signal ribbon* so the user can see exactly how the score was earned. The LLM's only role is qualitative tie-breaks when scores are within 5 points and natural-language presentation.

**OAuth in the MCP server, not the agent.** Calendar credentials live entirely inside the Calendar MCP server via `CALENDAR_TOKEN_JSON`. The scheduling agent has no auth responsibilities. Real-calendar mode is a single env-var flip.

**Outreach as artifact, not action.** YouTube doesn't expose creator emails, so the outreach feature **drafts a personalized DM** the user copies and sends through whichever channel they actually use (channel About page, business inquiry form, agency rep). Honest framing, more useful in real life.

---

## Features

| | |
|---|---|
| **YouTube Creator Discovery** | Multi-query search with synonym expansion, dedup, min-1K-subs filter, Shorts detection. Quota-conscious by default. |
| **Deterministic 8-signal scoring** | 100-pt fit score across engagement, audience, relevance, geo, activity, maturity, recency, quality. Visible signal ribbon in the UI. |
| **Media Kit Generation** | Auto-built brand-facing creator profile — subs, views, engagement rate, top topics, recent video highlights, collaboration formats. |
| **Calendar Scheduling** | Modal date / time / duration / timezone picker. Stub mode (demo) + real Google Calendar OAuth mode for live Meet links. |
| **Personalized Outreach Drafter** | One-click AI-drafted DM via Vertex Gemini. Mode-aware: brand→creator OR creator→brand voice. References a specific recent video. Copy-to-clipboard. |
| **Iterative Refinement Loop** | After initial results, user can add a constraint ("EU-only", "exclude Shorts-heavy") and re-run. Agent detects contradictions. |

---

## Production migration path

The demo runs on **SQLite** for portability and zero infrastructure overhead. Match data is seeded from `infra/schema.sql` at container startup; persistence is per-revision.

The next step is to implement the **AlloyDB Postgres** migration — connection management, Postgres-flavored schema, and environment-based credentials. This is the substrate for the next architectural step:

> **pgvector + 768-dim text embeddings** for hybrid keyword + semantic similarity matching, replacing the current keyword-overlap relevance scorer with a fused signal that catches meaning-based matches even when exact keywords don't overlap.

That work is planned for the post-hackathon v2 release.

---

## Tech stack

| Layer | What |
|---|---|
| Agent framework | `google-adk` ≥ 1.0 — root agent + 2 sub-agents |
| Model | `gemini-2.5-flash` via Vertex AI (`europe-west1`) — fallback to AI Studio for local dev |
| MCP | stdio MCP — YouTube Data API v3 (4 tools), Google Calendar API (3 tools) |
| Database | SQLite — 10 brand campaigns with brand-voice descriptions, match results, history |
| Frontend | Custom HTML / CSS / JS — Newsreader serif + Inter + JetBrains Mono. No framework dependencies. |
| Deployment | Docker → Cloud Run via `deploy.sh`. Vertex AI as the runtime backend. |
| Quality | 10-case golden eval harness (`tests/eval_scoring.py`) — locks in scoring behavior across signal-weight changes. |

---
## Deployment to Cloud Run

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

chmod +x deploy.sh
export YOUTUBE_API_KEY=$(grep "^YOUTUBE_API_KEY=" sponsorship_bridge/.env | cut -d= -f2 | tr -d '"' | tr -d "'" | tr -d ' \t\r\n')
./deploy.sh
```

The script enables required APIs, builds the container, deploys, and prints the service URL.

For real Google Calendar mode (live Meet links instead of stub):

```bash
python3 backend/auth_setup.py   # generates token.json via OAuth
USE_REAL_CALENDAR=true CALENDAR_TOKEN_JSON="$(cat token.json)" ./deploy.sh
```


## Local development

**Prerequisites:** Python 3.10+, a [Google AI Studio API key](https://aistudio.google.com/apikey) (free tier works), and a YouTube Data API v3 key.

```bash
git clone https://github.com/MabelHsu/sponsorship-bridge-public.git
cd sponsorship-bridge-public

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Configure `.env`:

```bash
cp .env.example sponsorship_bridge/.env
# Edit sponsorship_bridge/.env with real values
```

Initialize the database and run:

```bash
python3 backend/db_tools.py
python3 backend/api_server.py
```

Open http://localhost:8080.

---

---

## Project structure

```
sponsorship-bridge-public/
├── sponsorship_bridge/        ← ADK agent package
│   ├── agent.py                 # Root + analytics + scheduling agents
│   ├── scoring.py               # 8-signal deterministic scorer + media kit
│   ├── tools.py                 # date helpers
│   └── __init__.py
├── backend/
│   ├── api_server.py            # FastAPI server: /api/score, /api/agent-run, /api/outreach-draft, ...
│   ├── db_tools.py              # SQLite layer for brand campaigns + match history
│   └── auth_setup.py            # One-time OAuth setup for real Calendar mode
├── youtube_mcp_server/
│   └── server.py                # MCP server: search, channel details, videos, resolve
├── calendar_mcp_server/
│   └── server.py                # MCP server: check availability, create meeting, list events
├── ui/
│   ├── index.html               # Editorial dossier UI
│   ├── style.css                # Newsreader + Inter + JetBrains Mono
│   └── script.js                # Hero/runner cards, modals, refinement loop, outreach
├── infra/
│   └── schema.sql               # Brand campaigns + matches tables, 10 seeded brands
├── tests/
│   └── eval_scoring.py          # 10 golden test cases for the scorer
├── Dockerfile
├── deploy.sh
├── requirements.txt
├── .env.example
└── README.md
```

---

## Eval harness

```bash
python -m tests.eval_scoring
```

Runs 10 hand-curated scenarios (eco-skincare, tech vs beauty mismatch, geography mismatch, synonym expansion, sub-1K gating, inactive channel, Shorts-heavy, perfect fit, engagement outliers) and asserts each lands in its expected score band with the right risk flags. Exit 0 on pass, 1 on fail. CI-ready.

---

## Responsible AI

- **Brand safety**: Gemini evaluates channel content against the brief before recommending; risk flags surface inactivity, Shorts-heavy patterns, weak topical overlap, hidden subscriber counts.
- **Grounded responses**: All recommendations cite real YouTube data — subs, views, engagement rates from the API.
- **No PII storage**: Only public channel metadata is used.
- **Transparent scoring**: Every match includes the 8-component breakdown, plain-English reasoning, and explicit risk flags. The signal ribbon in the UI shows exactly how each point was earned.
- **Deterministic where it matters**: The scoring math is code; only qualitative tie-breaks and presentation are LLM-driven, ensuring reproducibility.
- **Honest framing on outreach**: We generate a draft, not an automated send. Users still review and dispatch through their own channels.

---

## Team

| | |
|---|---|
| **Mabel Hsu** | Product direction, architecture, scoring engine, MCP integrations, UI/UX, deployment, eval harness, presentation. [GitHub](https://github.com/MabelHsu) · [LinkedIn](https://www.linkedin.com/in/promabel/) |
| **Rusiru Dineth Jayasinghe** | Responsible for repository organization and documentation maintenance. [GitHub](https://github.com/rusi-din) · [LinkedIn](https://www.linkedin.com/in/rusiru-dineth/) |

---

*Gen AI Academy APAC 2026 — Cohort 1 Hackathon*
