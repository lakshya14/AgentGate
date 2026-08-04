# System Architecture & Tradeoffs

This document logs significant architectural decisions and tradeoffs made during the development of AgentGate. These serve as prime **System Design Interview** talking points.

## 1. State Persistence & Checkpointing
* **Decision:** Used LangGraph's `PostgresSaver` (with `psycopg3` and `AsyncConnectionPool`) backed by a Neon Serverless Postgres instance.
* **Tradeoff / Rationale:** 
  - Instead of managing state in-memory (which is lost on server restart), the checkpointer saves a binary blob of the exact state after every node executes.
  - This allows the graph to halt safely, wait for a human-in-the-loop (e.g., Discord approval), and resume exactly where it left off, even if the backend process crashes or restarts in the meantime.
  - **Why blob storage?** Using a generic schema (`thread_id`, `checkpoint_blob`) prevents us from having to run complex SQL schema migrations every time we add a new field to `AgentState`.

## 2. Database Schema Management & Migrations
* **Decision:** Implemented Alembic for version-controlled schema migrations on a Neon Serverless Postgres instance.
* **Tradeoff / Rationale:**
  - **Alembic over `create_all`:** While `Base.metadata.create_all()` is fine for prototyping, it cannot safely alter existing tables (e.g., adding columns without dropping data). Alembic provides version-controlled, rollback-capable migrations.
  - **Selective Management:** The database contains tables managed by SQLAlchemy (`github_events`, `audit_logs`) alongside tables managed automatically by LangGraph (`checkpoints`, etc.) and pgvector. We configured Alembic to strictly ignore these unmanaged third-party tables via the `include_object` filter in `env.py` to prevent destructive drops.

## 3. Asynchronous Database Connections
* **Decision:** Implemented `AsyncConnectionPool` inside the FastAPI `lifespan` event.
* **Tradeoff / Rationale:**
  - Initializing a new database connection per request incurs massive TCP/TLS handshake overhead. A connection pool keeps connections warm.
  - Moving the pool to the `lifespan` event ensures it is initialized once at startup and closed gracefully at shutdown, rather than being spun up per webhook request or per graph compilation. This maximizes throughput for high-traffic event processing.

## 3. Human-in-the-Loop via LangGraph Interrupt
* **Decision:** Used `interrupt_before=["execute_action"]` when compiling the graph, combined with `aupdate_state` + `ainvoke(None)` to resume from the Discord router.
* **Tradeoff / Rationale:**
  - The alternative would be to implement a custom polling loop or store a "pending approval" record and query it on each Discord interaction — both are fragile and stateful in the application layer.
  - LangGraph's interrupt mechanism keeps all pending state inside the Postgres checkpoint. The Discord interaction handler can resume execution with a single `ainvoke(None, config={"thread_id": ...})` call, making the control flow simple and auditable.
  - **Thread ID as correlation key:** Each GitHub event creates a unique `thread_id` (passed as the `configurable` key). The Discord button encodes this ID in its `custom_id`, so the approval is trivially matched back to the correct graph run without a lookup table.

## 4. Semantic Search with pgvector
* **Decision:** Stored issue embeddings (768-dimensional, `text-embedding-004`) in a `pgvector` column in the same Postgres database, using cosine similarity for retrieval.
* **Tradeoff / Rationale:**
  - A dedicated vector DB (e.g., Pinecone, Weaviate) would add another external dependency and cost. Since we already depend on Postgres for checkpointing and audit logs, co-locating the vector store keeps the infrastructure footprint minimal.
  - **Why cosine distance over L2?** Issue summaries vary in length. Cosine similarity normalizes for magnitude, making it more robust when comparing a one-line issue title against a detailed multi-paragraph description.
  - Graceful degradation: the vector store functions catch all exceptions and return a mock result if the DB is offline, preventing the research node from blocking the entire pipeline.

## 5. Dual-Webhook Security Model
* **Decision:** Two separate signature verification strategies are used — one per external event source.
  - **GitHub webhooks** → HMAC-SHA256 (`X-Hub-Signature-256` header), verified as a FastAPI dependency injected at the router level.
  - **Discord interactions** → Ed25519 asymmetric signature (`X-Signature-Ed25519` + `X-Signature-Timestamp`), verified inside the route handler using `PyNaCl`.
* **Tradeoff / Rationale:**
  - These are industry-standard schemes mandated by each platform; we have no choice but to implement both correctly.
  - Applying GitHub verification as a `Depends()` at the router level means it applies automatically to all current and future routes under `/webhook/github` without per-route boilerplate — a clean separation of concerns.
  - Discord's Ed25519 check must be done *before* parsing JSON (the raw bytes must be verified), which is why it lives at the top of the route handler rather than as a dependency.

## 6. Structured LLM Output with Pydantic
* **Decision:** Used `llm.with_structured_output(PydanticModel)` instead of prompting for free-text JSON and parsing it manually.
* **Tradeoff / Rationale:**
  - Free-text JSON from an LLM is fragile — the model may wrap it in markdown fences, add commentary, or produce invalid JSON under adversarial inputs.
  - `with_structured_output` leverages the model's native function-calling / tool-use capability to guarantee a valid, schema-conformant response. This eliminates an entire class of parsing errors and makes the node outputs deterministic and type-safe.

## 7. Containerisation & Local Deployment
* **Decision:** Containerised the app with a single `Dockerfile` and a `docker-compose.yml` orchestrating two services: `agent` (FastAPI) and `db` (Postgres + pgvector).
* **Tradeoff / Rationale:**
  - **Non-root user in Dockerfile:** The app runs as `appuser` instead of `root`. If an attacker exploits the application, they get a restricted user inside the container rather than root access to the host OS — a standard container hardening practice.
  - **Layer caching strategy:** `pyproject.toml` is copied and dependencies installed *before* the application code is copied. Since code changes far more frequently than dependencies, Docker reuses the cached `pip install` layer on subsequent builds — cutting rebuild times from minutes to seconds.
  - **`depends_on` in Compose:** Ensures the `db` container is started before the `agent` container boots, preventing connection errors during a cold `docker compose up`.
  - **`env_file` over hardcoded vars:** The `agent` service reads its configuration from `.env` via `env_file:`, keeping secrets out of `docker-compose.yml` and Git history entirely.
  - **Single pgvector DB image:** Rather than running a dedicated vector database (e.g., Pinecone, Weaviate) alongside Postgres, `ankane/pgvector` bundles the extension directly into the Postgres image. One database serves checkpoints, audit logs, and vector search — zero extra infrastructure.

## 8. Automated Node Retries & Error Recovery
* **Decision:** Implemented LangGraph's native `RetryPolicy` with exponential backoff on all network-dependent nodes (`classify`, `research`, `draft_action`, `execute_action`).
* **Tradeoff / Rationale:**
  - When LLM APIs or GitHub rate limits fail transiently, standard Python exception handling would crash the entire graph execution.
  - LangGraph's `RetryPolicy` catches these exceptions at the framework level and suspends the node for an exponential backoff period (e.g., 2s, 4s, 8s).
  - Because it is checkpoint-aware, it resumes execution *from the exact node that failed*, rather than restarting the entire graph from the beginning. This saves substantial LLM token costs and prevents duplicate work compared to a naive `@retry` decorator on the entire workflow.
