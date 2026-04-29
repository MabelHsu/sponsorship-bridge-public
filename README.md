# Sponsorship Bridge

> A **domain-specific multi-agent productivity assistant** built with **Google ADK**, **Gemini 2.5 Flash**, and **MCP** — automating the end-to-end workflow of brand-creator sponsorship matching: discovery, evaluation, and scheduling.

Built for **Gen AI Academy APAC 2026** — Cohort 1 Hackathon.

---

## What This Does

Sponsorship Bridge is a **Tinder-like two-sided matching app for brands and YouTube creators**. Brands can find creator partners, and creators can find sponsor opportunities. It demonstrates the same core patterns the hackathon brief calls for — multi-step task execution, structured data storage, multi-tool MCP integration, and agent coordination — applied to a concrete domain where those capabilities create real value.

The system is deliberately **end-to-end**: it doesn't just find candidates, it evaluates them, explains its reasoning, stores the result, and books the follow-up meeting — the full workflow a human coordinator would otherwise do manually across multiple tools.

Three collaborating AI agents handle the work:

**Brand Mode** — A brand describes their campaign and gets a ranked Top 3 shortlist of YouTube creators with fit scores, engagement analysis, qualitative tie-break reasoning, and a full media kit for the top match.

**Creator Mode** — A creator describes their channel and gets ranked sponsor opportunities from the SQLite brand campaign database, pitch angles, risks, and an auto-generated media kit.

**Scheduling** — After a match, the system schedules intro calls between brands and creators via Google Calendar.

**Dossier & Custom Prompting** — Build a persistent inventory of creators and brands across sessions, stored in a persistent backend, and use them as context for custom Gemini-powered outreach and strategy generation.

---

## What's new in Phase 2

Phase 1 proved the multi-agent matching workflow works. Phase 2 made it
production-shaped, transparent, and end-to-end.

### Product

- **Personalized Outreach Drafter (new)** — One-click AI-drafted DM via Vertex Gemini
  for the top match (or any of the top 3). Mode-aware: brand-to-creator pitch in
  brand mode, creator-to-brand pitch in creator mode. References a specific recent
  video for authenticity. Copy-to-clipboard for the user to send through whichever
  channel they actually use to reach creators.
- **Iterative Refinement Loop (new)** — After initial results, the user can add a
  one-line constraint ("EU-based only", "exclude Shorts-heavy", "prefer micro-creators
  under 100K") and re-run. Mode-aware suggestion chips. The agent detects
  contradictory refinements and warns the user before re-running.
- **Schedule modal with date/time picker** — Replaces the previous text-only
  scheduling prompt. Date, time, duration, and timezone fields. Triggers the live
  scheduling agent and produces a real Google Meet link in real-calendar mode.
- **10 brand campaigns with brand-voice descriptions** (was 5) — Spanning Beauty,
  Tech, Fitness, Travel, Home, Food & Beverage, Gaming, Finance, Pets. Each row
  carries a marketing-voice description that drives the creator-mode dossier copy.
- **Dossier — collect-and-strategize workspace (new)** — A sliding side drawer
  lets users save creator and brand matches into a working set, then ask a
  specialized Gemini sub-agent strategic questions over the saved items
  (e.g. *"draft a co-branded campaign idea using Creator A's audience and
  Creator B's style for Brand X"* or *"summarize the shared risks across these
  three creators"*). Session-keyed persistence so the Dossier survives a refresh.

### Transparency

- **Editorial dossier UI** — Custom HTML/CSS/JS rebuild. Newsreader serif + Inter
  + JetBrains Mono. Two-panel match view with a central seam fit numeral.
- **Visible signal ribbon** — Every match's 8 scoring components (engagement 25,
  audience 25, relevance 20, geography 10, activity 5, maturity 5, recency 5,
  quality 5) are rendered as proportionally-sized colored bands the user can see
  at a glance. No more black-box scoring.
- **Live agent trace panel** — The pipeline of tool calls (search, score, save,
  draft, schedule) shows up in the UI alongside the result, collapsible so it
  doesn't compete with the matches.

### Quality

- **10-case golden eval harness** at `tests/eval_scoring.py` — Locks in scoring
  behavior across signal-weight changes. Cases cover same-niche match, cross-niche
  mismatch, geography hit/miss, synonym expansion, sub-1K subscriber gating,
  inactive channels, Shorts-heavy patterns, perfect-fit, engagement-only outliers.
  Pytest-style runner, exits 0 on pass, 1 on fail. CI-ready.

---

## Hackathon Alignment

The problem statement asks for a multi-agent AI system that helps users **manage tasks, schedules, and information** by interacting with **multiple tools and data sources**. Here is how Sponsorship Bridge addresses each requirement:

| Requirement | Implementation |
|---|---|
| Primary agent coordinating sub-agents | `root_agent` orchestrates `analytics_agent` (DB reads) and `scheduling_agent` (Calendar) |
| Structured data storage and retrieval | SQLite database stores brand campaigns and all match results via `db_tools.py` |
| Multiple MCP tool integrations | Two MCP servers: YouTube Data API v3 (4 tools) + Google Calendar (3 tools), both via stdio |
| Multi-step workflow execution | Brand Mode: search → score → tie-break → media kit → save → schedule — all in one flow |
| API-based deployment | Deployed to Google Cloud Run; accessible via REST API |

The domain — sponsorship matching — is a stand-in for any complex business workflow that requires **information retrieval, evaluation, and calendar coordination**. The same architecture would apply to recruiting workflows, vendor selection, or any task where an agent must search external data, score and rank options, persist results, and schedule follow-ups.

---

## Database choice — SQLite for demo, AlloyDB for production

The submission deploys on **SQLite** because it is portable, ships inside the
container with zero infrastructure overhead, and stays at $0 across the entire
judging window. Match data is seeded from `infra/schema.sql` at container startup
so every fresh revision boots with the same 10 brand campaigns.

For production, **AlloyDB for PostgreSQL** is the right choice — and we evaluated
it deliberately during Phase 2. The full technical case lives in
[`alloydb.md`](alloydb.md), but in short:

- **Vector search via `pgvector`** — semantic match brand briefs against creator
  content, so a brand seeking "vegan beauty" still ranks a "plant-based cosmetics"
  creator even when keywords don't overlap. This is the v2 scoring upgrade.
- **AlloyDB AI integration with Vertex AI** — call Gemini directly from SQL to
  generate fit summaries inside the database layer, reducing app-server round-trips.
- **Columnar engine for analytical queries** — up to 100x faster filtering across
  industry, audience, budget, engagement when the dataset grows past thousands of
  rows.
- **HTAP for real-time market intelligence** — analyze match history and trends
  without a separate data warehouse.

The trade-off for a hackathon submission is cost: a hosted AlloyDB cluster
runs ~$22/day even at the smallest 2-vCPU tier with high availability, and you
cannot fully shut it down without deleting the cluster. Across a multi-day
judging window that is non-trivial personal billing, and the visible UI/agent
behavior is identical whether SQLite or AlloyDB is behind it. So we shipped on
SQLite and prototyped the migration on a separate branch — see
[`alloydb-omni`](../../tree/alloydb-omni) for the connection layer, Postgres
schema, and env-based credentials. AlloyDB Omni (the free Docker-based variant)
is the local-development path for the v2 work; hosted AlloyDB is the production
target.

---

## Key Feature: The Dossier & AI Strategy Engine

Beyond simple matching, the **Dossier** provides a workspace for "collecting" top candidates and using them as a structured context for advanced AI tasks.

1.  **Session Persistence**: Unlike standard web apps that lose state on refresh, Sponsorship Bridge uses a session-keyed persistent backend (`session_dossier`) to remember your selections across browser restarts.
2.  **Strategic Prompting**: A specialized Gemini 2.5 Flash sub-agent can be "instructed" through the Dossier. Because the agent has access to the full structured data of every selected item, it can perform complex reasoning like:
    *   *"Draft a co-branded campaign idea that leverages Creator A's audience and Creator B's style for Brand X."*
    *   *"Summarize the common risks across these three creators."*
3.  **Editorial Workspace**: The UI features a dual-panel sliding drawer system. The main Dossier manages your inventory, while a secondary "Response Panel" provides a premium, typography-focused reading experience for AI-generated strategy and outreach drafts.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     Sponsorship Bridge (Root Agent)                          │
│                     Gemini 2.5 Flash via Vertex AI                           │
│                                                                              │
│   Owns: YouTube MCP tools, score_creator_fit, generate_media_kit,            │
│         save_match_result                                                    │
│                                                                              │
│   Runs full Brand Mode flow directly:                                        │
│   Search → Score → tie-break → Media kit →                                   │
│   Delegates history reads and scheduling to sub-agents                       │
└────────────────┬────────────────────────────────────┬────────────────────────┘
                 │                                    │
          ┌──────▼───────┐                    ┌───────▼────────┐
          │  Analytics   │                    │   Scheduling   │
          │   Agent      │                    │    Agent       │
          │              │                    │                │
          │ get_campaigns│                    │ Calendar MCP   │
          │ get_history  │                    │ Tools          │
          └──────────────┘                    └────────────────┘
                  │                                   │             
        Root Agent direct MCP path          Scheduling Agent MCP path
                  │                                   │
             MCP (stdio)                          MCP (stdio)
                  │                                   │
      ┌───────────▼────────────┐         ┌────────────▼──────────────┐
      │    YouTube MCP Server  │         │    Calendar MCP Server    │
      │  • search_creators     │         │  • check_availability     │
      │  • get_channel_details │         │  • create_meeting         │
      │  • get_channel_videos  │         │  • list_upcoming_events   │
      │  • resolve_channel     │         └────────────┬──────────────┘
      └────────────┬───────────┘                      │
                   │                          Google Calendar API
          YouTube Data API v3
```

### Agent Responsibilities

| Agent | Role | Owns |
|-------|------|------|
| **Root Agent** | Orchestrator — runs full Brand Mode flow including tie-breaks | YouTube MCP tools, `score_creator_fit`, `generate_media_kit`, `save_match_result` |
| **Analytics Agent** | Database reads and market intelligence | `get_active_brand_campaigns`, `get_match_history` |
| **Scheduling Agent** | Books intro calls after a match | Calendar MCP: `check_availability`, `create_meeting`, `list_upcoming_events` |

### Key Design Decisions

**Why Root Agent Owns YouTube + Scoring + Tie-Breaks**

In ADK 1.x, sub-agent responses surface directly to the user. If YouTube search or qualitative judgment lived in a sub-agent, raw data or intermediate analysis would be shown to the user before the root agent could format and present it. By keeping all YouTube MCP tools, scoring tools, and tie-break logic on the root agent, it controls the full Brand Mode flow in one turn — search, filter, score, tie-break, media kit, save — and only presents the final polished results.

**Why OAuth Lives in the MCP Server, Not the Agent**

The scheduling agent handles workflow and slot decisions only. Google Calendar authentication is managed entirely inside the Calendar MCP server via a pre-generated token stored as the `CALENDAR_TOKEN_JSON` environment variable. The agent has no auth responsibilities. This keeps responsibilities clean, avoids mixing backend concerns into the agent layer, and means the real-calendar upgrade requires no changes to `agent.py`.

**Deterministic Scoring**

`score_creator_fit` is fully deterministic — code computes all 100 points. The LLM handles what LLMs do best: qualitative tie-breaks when scores are close, and presenting results in natural language. No arithmetic is delegated to the model.

Scoring breakdown (100 pts):
- 25 pts — engagement rate ((likes + comments) / views, with view/subscriber fallback)
- 25 pts — audience size (log scale, 1K–500K)
- 20 pts — relevance (keyword overlap with synonym expansion)
- 10 pts — geography match (country / region / global)
- 5 pts — content activity (recent videos + posting frequency)
- 5 pts — channel maturity (total video count)
- 5 pts — recency (days since last post)
- 5 pts — quality tiebreaker (fewer risk flags = higher score)

### Key Technologies

| Requirement | Implementation |
|-------------|---------------|
| **ADK** | `google-adk` — root agent + 2 sub-agents |
| **Gemini** | `gemini-2.5-flash` via Vertex AI (`europe-west1`) |
| **MCP** | YouTube Data API via stdio MCP server + Google Calendar via stdio MCP server |
| **GCP** | Cloud Run (deployment), Vertex AI (model), YouTube API, Cloud Build |
| **Database** | SQLite for the demo (10 brand campaigns + match history via `db_tools.py`); AlloyDB Postgres + `pgvector` planned for v2 — see [`alloydb.md`](alloydb.md) and the [`alloydb-omni`](../../tree/alloydb-omni) prototype branch |

---

## Project Structure

```
sponsorship-bridge/
├── sponsorship_bridge/       ← ADK agent package (root)
│   ├── agent.py              # All agents + tools defined here
│   ├── __init__.py           # Exports root_agent
│   └── .env                  # API keys (not committed)
├── youtube_mcp_server/       ← MCP server for YouTube API
│   ├── server.py             # FastMCP with 4 YouTube tools
│   └── __init__.py
├── calendar_mcp_server/      ← MCP server for Google Calendar
│   ├── server.py             # FastMCP with 3 Calendar tools
│   └── __init__.py
├── infra/
│   └── schema.sql            # SQLite schema with mock brand data
├── tests/
│   └── eval_scoring.py       # 10 golden test cases for the deterministic scorer
├── auth_setup.py             # One-time OAuth setup for real Calendar
├── db_tools.py               # SQLite tools for the agent
├── requirements.txt
├── Dockerfile
├── deploy.sh
├── .env.example
├── .gitignore
├── README.md
└── alloydb.md                # Production-database rationale (v2 plan)
```

---

## Setup and Deployment

### Option A — Cloud Shell with Vertex AI (Production)

> For team members with GCP project access.

**Prerequisites:**
- Google Cloud project with billing enabled
- [Cloud Shell](https://shell.cloud.google.com)
- YouTube Data API v3 key

**1. Clone and configure**

```bash
git clone https://github.com/MabelHsu/sponsorship-bridge.git
cd sponsorship-bridge
```

**2. Enable required APIs**

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  youtube.googleapis.com \
  calendar-json.googleapis.com
```

**3. Set up environment**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example sponsorship_bridge/.env
```

Edit `sponsorship_bridge/.env`:

```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=europe-west1
GOOGLE_GENAI_USE_VERTEXAI=TRUE
YOUTUBE_API_KEY=your-api-key-here
```

**4. Authenticate**

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

**5. Initialize the database**

```bash
python3 backend/db_tools.py
```

**6. Launch the demo UI**

```bash
python3 backend/api_server.py
```

Open `http://localhost:8080`. The UI uses deterministic local scoring and
SQLite persistence, so it is safe for demos even when YouTube quota is low.

To use the raw ADK playground instead:

```bash
adk web --port 8080 --allow_origins "*"
```

> ⚠️ The `--allow_origins "*"` flag is required in Cloud Shell. Without it, all requests return `403 Forbidden` with no error message in the UI.

**7. Deploy to Cloud Run  (Production)**

You can deploy the system in two modes:

**Option A: Stub Calendar Mode (Default)**
Uses placeholder calendar data. Safe for testing and development.
```bash
chmod +x deploy.sh
export YOUTUBE_API_KEY="your-youtube-api-key"
./deploy.sh
```

**Option B: Real Calendar Mode**
Connects to a real Google Calendar to generate live Google Meet links.

Run python3 auth_setup.py locally to generate your token.json OAuth file.

Deploy by passing the token directly into the environment:
```bash
export YOUTUBE_API_KEY="your-youtube-api-key"
USE_REAL_CALENDAR=true CALENDAR_TOKEN_JSON="$(cat token.json)" ./deploy.sh
```

---

### Option B — Local with Google AI Studio (Free, No GCP)

> For team member who cannot access the GCP project. Uses the same model (`gemini-2.5-flash`) with no billing required.

**Prerequisites:**
- Python 3.10+
- A [Google AI Studio API key](https://aistudio.google.com/apikey) (free)
- YouTube Data API v3 key (shared by Mabel)

**1. Clone and set up**

```bash
git clone git@github.com:MabelHsu/sponsorship-bridge.git
cd sponsorship-bridge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2. Configure `.env` for AI Studio**

```bash
cp .env.example sponsorship_bridge/.env
```

Edit `sponsorship_bridge/.env`:

```bash
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your-ai-studio-api-key-here
YOUTUBE_API_KEY=your-youtube-api-key-here
```

No `gcloud auth` commands needed.

**3. Initialize the database and Calendar MCP server**

```bash
python3 db_tools.py
mkdir -p calendar_mcp_server
cp calendar_server.py calendar_mcp_server/server.py
touch calendar_mcp_server/__init__.py
```

**4. Launch the demo UI**

```bash
python3 api_server.py
```

Open `http://localhost:8080`.

To use the raw ADK playground instead:

```bash
adk web --port 8080 --allow_origins "*"
```

Open `http://localhost:8080` and select `sponsorship_bridge`.

**AI Studio limitations:** Lower rate limits than Vertex AI. If you see `429 RESOURCE_EXHAUSTED`, wait 60 seconds and retry. Agent behavior is identical on both backends.

---

## Sample Interaction

**Brand Mode prompt:**
> "I'm an eco-friendly skincare brand targeting women 18-35 in the US. Find me YouTube creators who make skincare, clean beauty, or sustainable lifestyle content."

**Output:**
```
### Top 3 Creator Matches

1. **GreenGlowBeauty** — Fit Score: 92/100
   Subscribers: 380,000 | Engagement: 11.1% (High)
   Why: GreenGlowBeauty has 380,000 subscribers with high engagement.
   Content covers: eco beauty, skincare, sustainable living.
   Risks: Low risk

2. **NaturalSkinVlog** — Fit Score: 75/100
   Subscribers: 95,000 | Engagement: 19.5% (High)
   Why: Strong engagement. Content covers skincare, natural products, wellness.
   Risks: Creator geography unknown.

3. **CleanBeautyUS** — Fit Score: 68/100
   Subscribers: 210,000 | Engagement: 2.8% (Average)
   Why: Solid audience size. Content covers beauty and lifestyle.
   Risks: Low recent view-to-subscriber ratio.

---
**Media Kit — GreenGlowBeauty**

- **Creator:** GreenGlowBeauty
- **Channel:** https://www.youtube.com/channel/UC...
- **Subscribers:** 380,000
- **Total Views:** 8,400,000
- **Avg Views per Video:** 42,000
- **Country:** US
- **Top Topics:** eco beauty, natural skincare, sustainable living
- **Recent Highlights:** My 30-Day No-Plastic Challenge | Top 5 Clean Serums 2025
- **Collaboration Formats:** Dedicated video, Product integration, Giveaway, Brand ambassador
---

Want me to generate media kits for the other top creators?
Ready to schedule an intro call? Just say the word.
```

---

## Demo Prompts

```
# Brand Mode
"I'm an eco-friendly skincare brand targeting women 18-35 in the US.
Find me YouTube creators who make skincare, clean beauty, or sustainable lifestyle content."

"I'm a fitness supplement brand targeting men 25-40.
Find me fitness creators in Southeast Asia."

# Creator Mode
"I'm a creator. My channel https://www.youtube.com/channel/UCFQ_CWYmt-ScWaPX4YfnBrQ covers sustainable living and zero-waste lifestyle. What brands in your database would be a good match for me?"

# History
"Show me the match history."

# Scheduling
"Schedule an intro call between EcoGlow and the top creator for next Tuesday at 10am."
```

---

## Team Roles

| Who | Responsibility |
|-----|---------------|
| **Mabel** | Architecture design, core programming — root agent, orchestration, scoring tools, YouTube MCP server, Calendar MCP server, database layer, deterministic 8-signal scoring, refinement loop, outreach drafter, scheduling agent, eval harness, deployment, GCP infrastructure, presentation slides, demo script, documentation |
| **Rusiru** | Repository and documentation maintenance; developed the Dossier feature. Executed architectural PoC and technical evaluation for AlloyDB to prepare for future database migrations.

---

## Responsible AI Practices

- **Brand safety**: Gemini evaluates channel content against the brand brief before recommending
- **Grounded responses**: All recommendations cite real YouTube data (subscribers, views, engagement rates)
- **No PII storage**: Only public channel metadata is used
- **Transparent scoring**: Every match includes a plain-English explanation with actual numbers and risk flags
- **Deterministic scoring**: All 100 points are computed by code — no arithmetic is delegated to the LLM, ensuring reproducible and auditable results

---

## Lessons Learned

1. **Use Vertex AI, not AI Studio free tier, for production** — ADK agents make 4–6 Gemini calls per interaction. Free tier quota runs out fast. However, AI Studio works well for local development and testing.
2. **Model availability varies by region** — `gemini-2.5-flash` works in `europe-west1`. Check Model Garden for your region.
3. **Sub-agent responses surface directly to users in ADK 1.x** — tools that need to process data before presenting it must live on the root agent, not a sub-agent. This applies to YouTube discovery, scoring, and qualitative tie-breaks.
4. **Keep tie-break logic on the root agent** — a separate "scoring agent" with no tools adds a hand-off that risks leaking intermediate output to the user. Gemini 2.5 Flash is capable enough to do qualitative reasoning inline, and keeping it on the root agent ensures the full Brand Mode flow completes in one turn.
5. **OAuth belongs in the MCP server, not the agent** — the agent should handle workflow only. Authentication via `CALENDAR_TOKEN_JSON` is simpler, more stable, and closer to production patterns than interactive OAuth in the agent layer.
6. **FastMCP import** — use `from mcp.server.fastmcp import FastMCP`. The standalone `fastmcp` package is a different project and incompatible with google-adk.
7. **Cloud Shell auth** — run `gcloud auth application-default login` at the start of every Cloud Shell session.
8. **`--allow_origins "*"` is not optional** — without it, Cloud Shell blocks all ADK web requests with a silent 403.
9. **ADK supports dual backends** — the same agent code runs on both Vertex AI (production) and AI Studio (local dev) by changing one env var. This enabled productive parallel work even when team members couldn't share GCP access.

---

*Gen AI Academy APAC 2026 — Cohort 1 Hackathon*
*Team: Mabel + Rusiru*
