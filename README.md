# AgentGate 🤖

An **event-driven, autonomous GitHub issue triage agent** built with LangGraph, FastAPI, and Discord for human-in-the-loop approvals.

AgentGate listens for incoming GitHub webhook events, runs each new issue through a multi-step AI pipeline (ingest → classify → research → draft action), pauses to send a Discord approval request, then executes the approved action on GitHub.

### 📸 How it works
<div align="center">
  <img src="./agentGateDiscord.png" alt="AgentGate Discord Interaction" width="45%" />
  <img src="./agentgateFinal.png" alt="AgentGate Final Action" width="45%" />
</div>

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Agent Pipeline](#agent-pipeline)
- [API Endpoints](#api-endpoints)
- [Setup & Installation](#setup--installation)
- [Environment Variables](#environment-variables)
- [Running Locally](#running-locally)
- [Current Status](#current-status)

---

## Overview

When a new issue is opened on a GitHub repository, AgentGate:

1. **Receives** the webhook event and persists the raw payload to Postgres.
2. **Ingests** and normalizes the issue data into a structured state.
3. **Classifies** severity and suggests labels using a Gemini LLM.
4. **Researches** similar past issues via a pgvector cosine-similarity search.
5. **Drafts** a proposed action (`close`, `wait_for_human`) with a confidence score.
6. **Pauses** and sends an interactive Discord message with **Approve / Reject / Open Issue** buttons.
7. **Resumes** the graph after a human clicks a button and either executes the action or cancels it.
8. **Logs** every action taken to an audit table.

---

## Architecture

```
GitHub Webhook
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI  (main.py)                                     │
│  ┌──────────────────┐   ┌──────────────────────────┐   │
│  │ /webhook/github  │   │ /discord/interactions    │   │
│  │  (routers/)      │   │  (routers/)              │   │
│  └────────┬─────────┘   └────────────┬─────────────┘   │
│           │  persists                │  resumes graph   │
│           ▼  raw event               ▼                  │
│  ┌─────────────────┐   ┌─────────────────────────────┐ │
│  │  Postgres DB    │   │  LangGraph Agent (agent/)   │ │
│  │  github_events  │   │  ┌─────────────────────┐   │ │
│  │  audit_logs     │   │  │ ingest → classify   │   │ │
│  │  embedded_issues│   │  │   → research        │   │ │
│  │  (checkpoints)  │   │  │   → draft_action ──►│───┼─┼──► Discord
│  └─────────────────┘   │  │   [INTERRUPT]       │   │ │
│                         │  │   → execute_action  │   │ │
│                         │  └─────────────────────┘   │ │
│                         └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

State is persisted in Postgres via `AsyncPostgresSaver` (LangGraph checkpointer), enabling the graph to survive server restarts between the interrupt and the human's approval.

> See [architecture.md](./architecture.md) for deeper architectural decisions, data-flow details, and tradeoffs.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI + Uvicorn |
| Agent Orchestration | LangGraph (StateGraph) |
| LLM | Google Gemini (`gemini-3.6-flash`) |
| Embeddings | Google `text-embedding-004` (768-dim) |
| Database | PostgreSQL (Neon Serverless) |
| Vector Search | pgvector (cosine similarity) |
| ORM | SQLAlchemy 2.0 |
| State Persistence | LangGraph `AsyncPostgresSaver` |
| Discord Integration | Discord Bot API v10 (Ed25519 sig verification) |
| GitHub Integration | GitHub REST API + HMAC-SHA256 webhook verification |
| Config | pydantic-settings |
| Logging | structlog |
| HTTP Client | httpx (async) |
| Containerisation | Docker + Docker Compose |
| CI/CD & Deployment | GitHub Actions + Fly.io (Scale-to-Zero) |

---

## Project Structure

```
AgentGate/
├── main.py                  # FastAPI app, lifespan, DB pool, router registration
├── config.py                # pydantic-settings — reads from .env
├── database.py              # SQLAlchemy engine + SessionLocal + Base
├── models.py                # ORM models: GithubEvent, AuditLog
├── schemas.py               # Pydantic request/response schemas
├── dependencies.py          # FastAPI dependency: verify_github_signature (HMAC-SHA256)
│
├── routers/
│   ├── __init__.py
│   ├── github.py            # POST /webhook/github — receives & persists events
│   └── discord.py           # POST /discord/interactions — handles button clicks, resumes graph
│
├── agent/
│   ├── state.py             # AgentState TypedDict (full state schema)
│   ├── graph.py             # build_graph() — StateGraph wiring + AsyncPostgresSaver
│   ├── nodes.py             # ingest, classify, research, draft_action, execute_action
│   ├── tools.py             # GitHub REST API helpers (get_issue, post_comment, add_labels, etc.)
│   ├── notifications.py     # Discord messaging (send_approval_message, update_approval_message)
│   └── vector_store.py      # pgvector store: embed, store, and search similar issues
│
├── smoke_test.py            # Basic integration smoke test
├── test_checkpoint.py       # Checkpoint persistence verification
├── practice.py              # Practice / scratch file
├── pyproject.toml           # Project metadata and dependencies
├── .env.example             # Example environment variables
└── architecture.md          # Architectural decisions & tradeoffs
```

---

## Agent Pipeline

The LangGraph `StateGraph` executes the following linear pipeline, with a **mandatory interrupt** before `execute_action`:

```
START
  │
  ▼
ingest_node
  Extracts issue_number, issue_title, and issue_body from the raw webhook payload.
  │
  ▼
classify_node
  Calls Gemini with structured output to produce:
    - severity  (low / medium / high / critical)
    - suggested_labels  (list of GitHub label strings)
  │
  ▼
research_node
  Embeds the issue summary and queries pgvector for the top-3 most similar past issues.
  │
  ▼
draft_action_node
  Calls Gemini again with classification + research context to produce:
    - proposed_action  (close / wait_for_human)
    - action_rationale
    - confidence score
  Sends an interactive Discord message with Approve / Reject / Open Issue buttons.
  ─── GRAPH PAUSES HERE (interrupt_before=["execute_action"]) ───
  │
  ▼  (human clicks button → Discord router resumes graph)
execute_action_node
  Reads approval_status from state:
    - "approve" → executes the proposed GitHub action + logs to audit_logs
    - "reject"  → cancels action + logs to audit_logs
  │
  ▼
END
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/webhook/github` | Receives GitHub webhook events (HMAC-SHA256 verified) |
| `POST` | `/discord/interactions` | Handles Discord button interactions (Ed25519 verified) |

---

## Setup & Installation

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- A Postgres database with the `pgvector` extension enabled (e.g., [Neon](https://neon.tech) — free tier)
- A Discord Bot with Interactions endpoint configured
- A GitHub App or webhook with a shared secret

---

## 🚀 Quickstart — Run Locally with Docker

The fastest way to get the full stack running (API + database) locally.

**1. Clone the repo**
```bash
git clone <repo-url>
cd AgentGate
```

**2. Configure your environment**
```bash
cp .env.example .env
# Fill in your secrets in .env
```

**3. Boot the full stack**
```bash
docker compose up --build
```

This will:
- Build the `agent` image from the `Dockerfile`
- Pull the `ankane/pgvector` image for the `db` service
- Start both containers on a shared internal network
- Expose the API at `http://localhost:8000`

**4. Expose your local server for webhooks** 

Use [ngrok](https://ngrok.com/) or similar to receive real GitHub and Discord events:
```bash
ngrok http 8000
```

Then configure:
- **GitHub Webhook URL**: `https://<ngrok-url>/webhook/github`
- **Discord Interactions URL**: `https://<ngrok-url>/discord/interactions`

---

## ☁️ Live Deployment (Fly.io)

AgentGate is deployed in production on **Fly.io** using a **Scale-to-Zero** architecture. 

* **Webhook Endpoint:** `https://agentgate.fly.dev/webhook/github`
* **CI/CD:** Every push to `main` triggers a GitHub Actions pipeline that runs `ruff` (linting), `mypy` (type-checking), and `pytest` before automatically building and deploying the Docker container.
* **Cost Optimization:** The Fly.io container spins down to zero after inactivity. When a GitHub webhook arrives, Fly's proxy holds the request, cold-starts the FastAPI container in ~2 seconds, processes the agent workflow, and goes back to sleep.

---

## Running Locally (without Docker)

```bash
# Install in editable mode with all dependencies
pip install -e .

# Start the server
uvicorn main:app --reload --port 8000
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `GITHUB_WEBHOOK_SECRET` | Shared secret used to verify GitHub webhook HMAC-SHA256 signatures |
| `GITHUB_TOKEN` | Personal Access Token with read/write access to issues |
| `GITHUB_REPO` | Target repository in `owner/repo` format |
| `DATABASE_URL` | PostgreSQL connection string (e.g., `postgresql+psycopg://user:pass@host/db`) |
| `GEMINI_API_KEY` | Google Gemini API key |
| `DISCORD_PUBLIC_KEY` | Discord application public key for Ed25519 signature verification |
| `DISCORD_BOT_TOKEN` | Discord Bot token for sending/editing messages |
| `DISCORD_CHANNEL_ID` | Discord channel ID where approval messages are posted |

---
