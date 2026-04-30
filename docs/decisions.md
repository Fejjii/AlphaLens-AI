# Architectural decisions

Short ADR-style notes explaining the major stack choices. Each decision
is revisitable; the goal is to make trade-offs explicit.

## ADR-001: FastAPI for the backend

**Decision.** Use FastAPI as the HTTP framework.

**Why.**
- Native Pydantic v2 integration → request/response validation and
  OpenAPI generation come from the same models we use throughout the
  service layer.
- First-class async/await fits well with LLM, broker, and market-data
  calls that are I/O-bound.
- Mature ecosystem: dependency injection, middleware, lifespans,
  background tasks, WebSocket support.

**Alternatives considered.** Flask (no native async, no Pydantic),
Litestar (smaller community), Django (overkill for an API-first service).

## ADR-002: Next.js (App Router) for the frontend

**Decision.** Use Next.js 14 with the App Router and TypeScript.

**Why.**
- Server components reduce client JS for read-heavy dashboards.
- Built-in routing, layouts, streaming, and edge support.
- Largest React ecosystem; Tailwind + shadcn/ui slot in cleanly.
- `output: "standalone"` produces a small, container-friendly artifact.

**Alternatives.** Remix (smaller ecosystem), SvelteKit (team unfamiliar),
plain React + Vite (more wiring for routing/SSR).

## ADR-003: LangGraph for agent orchestration

**Decision.** Use LangGraph for multi-step agent workflows.

**Why.**
- State graphs are explicit and inspectable — better for debuggability
  and audit than ReAct loops or chain-of-tools.
- Built-in checkpointing supports human-in-the-loop approvals and time
  travel for investigations.
- Pluggable persistence (Redis/Postgres) for durable conversations.

**Alternatives.** LangChain agents (less structured state), CrewAI
(higher-level, less control), bespoke orchestration (reinventing
checkpointing).

## ADR-004: Qdrant for the vector store

**Decision.** Use Qdrant for embeddings and similarity search.

**Why.**
- Open-source, self-hostable, simple operationally.
- Strong filtering on payloads (essential for tenant- and policy-aware
  retrieval).
- HNSW with quantization options scales to millions of vectors per
  collection.

**Alternatives.** pgvector (simpler but slower at scale, weaker
filtering), Pinecone (managed, vendor lock-in), Weaviate (heavier
footprint).

## ADR-005: Redis for cache, queues, and agent checkpoints

**Decision.** Use Redis 7 for ephemeral state.

**Why.**
- Low-latency cache for market data, rate limits, idempotency keys.
- Lightweight queue/pubsub for agent task coordination.
- LangGraph can checkpoint to Redis for fast conversation resume.

**Alternatives.** In-memory only (loses durability across restarts),
Memcached (no streams/pubsub), Kafka (overkill at current scale).

## ADR-006: Postgres as the system of record

**Decision.** Use Postgres 16 for durable state.

**Why.**
- ACID semantics for trades, approvals, audit trails.
- JSONB for semi-structured agent traces and tool I/O.
- Mature tooling (pgAdmin, pg_dump, logical replication, extensions).

**Alternatives.** MongoDB (weaker transactions for financial data),
DynamoDB (vendor lock-in, weaker ad-hoc query), MySQL (weaker JSON
support).

## ADR-007: Alpha Vantage as the optional market-data provider

**Decision.** Make Alpha Vantage an *optional* market-data provider behind
the `MarketDataClient` protocol, with a deterministic offline client as
the default.

**Why.**
- Local development, CI, and the demo environment must run without
  external API keys or network access. The deterministic fallback gives
  stable hash-derived prices that make tests reproducible.
- Alpha Vantage has a free tier suitable for prototyping; their
  `GLOBAL_QUOTE` endpoint covers what the agent needs (last price,
  previous close, change, change %, latest trading day).
- Keeping the integration provider-agnostic (single `MarketDataClient`
  protocol returning a normalized `MarketQuote`) means we can swap to
  IEX, Polygon, or a paid Bloomberg/Refinitiv adapter later without
  touching the agent or the tool surface.
- Selection is gated by both `MARKET_DATA_PROVIDER` and
  `ALPHA_VANTAGE_API_KEY`: misconfigurations degrade to the fallback
  rather than crashing the agent. Provider errors (rate limits,
  timeouts, malformed payloads) are caught at the service layer and
  also fall back per-call, so a flaky upstream never breaks `/agent/chat`.

**Alternatives.** yfinance (unofficial, scraping-prone, terms ambiguous),
IEX Cloud (deprecated for retail), Polygon (paid for real-time), live
Bloomberg/Refinitiv (cost + procurement out of scope at this stage).

## ADR-008: Serper as the optional web/news search provider

**Decision.** Make Serper an *optional* web-search provider behind the
`SearchClient` protocol, with a deterministic offline client as the
default. The agent calls web search **in addition to** internal RAG —
never as a replacement.

**Why.**
- Public web/news context (earnings reactions, macro headlines, sector
  catalysts) is genuinely useful for investigations, but external
  dependencies must never break local development, CI, or the demo
  environment. The deterministic fallback returns hash-derived results
  shaped like real financial-news headlines, so the agent always has
  *some* external context to reason over.
- Serper offers a simple `POST /search` endpoint over Google results,
  with a free tier suitable for prototyping and a clean JSON contract
  (`organic[]`) that's easy to normalize.
- Keeping the integration provider-agnostic (single `SearchClient`
  protocol returning a normalized `SearchResponse`) means we can swap to
  Tavily, Bing, Brave, or a paid news API later without touching the
  agent or the tool surface.
- Selection is gated by both `SEARCH_PROVIDER` and `SERPER_API_KEY`;
  misconfigurations and provider failures (rate limits, timeouts,
  malformed payloads, HTTP errors) degrade to the fallback rather than
  crashing `/agent/chat`.
- RAG (internal knowledge base) and web search serve different needs:
  RAG provides authoritative, policy-aware internal context; web search
  provides freshness. The agent runs both when the message warrants
  external context, so reviewers see internal *and* public evidence
  side-by-side.

**Alternatives.** Tavily (newer, smaller index), Bing Search API
(Microsoft account + procurement friction), Brave Search (smaller
coverage), scraping Google directly (ToS + reliability).

## ADR-009: uv for Python dependency management

**Decision.** Use uv for the backend.

**Why.**
- Order-of-magnitude faster than pip + venv for installs.
- Lockfile + reproducible environments out of the box.
- Compatible with PEP 621 `pyproject.toml`.

**Alternatives.** Poetry (slower, heavier), pip-tools (manual lock
workflow).

## ADR-010: FRED as the optional macro-data provider

**Decision.** Make FRED (Federal Reserve Bank of St. Louis) an *optional*
macro-data provider behind the `MacroDataClient` protocol, with a
deterministic offline client (`FallbackMacroClient`) as the default.

**Why.**
- Macro context (interest rates, inflation, unemployment, GDP) is genuinely
  useful for investment investigations — particularly for trade ideas, risk
  checks, and market-news queries. Without macro data the agent is blind to the
  monetary and economic regime the portfolio operates in.
- Local development, CI, and the demo environment must run without external
  API keys or network access. The deterministic fallback returns hard-coded
  realistic values (sourced from actual late-2024 FRED releases) that keep
  tests reproducible and the agent always functional.
- FRED's REST API is free, stable, and authoritative. The
  `series/observations` endpoint covers all required series with a simple
  `GET` call that returns JSON. It is rate-limited but the agent only queries
  it on demand, so the free tier is sufficient for prototyping.
- Keeping the integration provider-agnostic (single `MacroDataClient` protocol
  returning normalized `MacroObservation` / `MacroSnapshot` models) means we
  can add Bloomberg, Refinitiv, or a paid macro-data vendor later without
  touching the agent or tool surface.
- Selection is gated by both `MACRO_DATA_PROVIDER=fred` **and**
  `FRED_API_KEY` being non-empty: misconfigurations and provider failures
  (rate limits, timeouts, malformed payloads, "." missing-value markers) all
  degrade to the fallback rather than crashing `/agent/chat`.
- The keyword heuristic in `gather_node` triggers `macro_snapshot` when the
  message contains macro-relevant terms (rates, inflation, CPI, GDP, Fed,
  recession, etc.). This is intentionally conservative and predictable; an LLM
  classification can add a `needs_macro` field later without structural changes.

**Alternatives.** World Bank API (less timely for US-specific rates),
yfinance macro proxies (unofficial, no guarantee of accuracy), OECD API
(wider coverage but higher latency and more complex schema), paid Bloomberg/
Refinitiv macro feeds (cost + procurement out of scope at this stage).

## ADR-011: SEC EDGAR as the optional filing-data provider

**Decision.** Make SEC EDGAR an *optional* filing-data provider behind the
`SECClient` protocol, with a deterministic offline client (`FallbackSECClient`)
as the default. Full SEC filing HTML/XBRL parsing is deferred.

**Why.**
- Official SEC filings (10-K, 10-Q) contain the most authoritative source of
  company risk factors, business descriptions, and management commentary. This
  context is directly useful for trade ideas, research queries, and risk
  investigations.
- EDGAR's public REST API (`data.sec.gov/submissions/CIK{cik}.json`) is free,
  requires no API key, and returns structured filing metadata (form types, dates,
  accession numbers) in JSON. The only requirement is a descriptive `User-Agent`
  header identifying the application and a contact email (EDGAR fair-access
  policy).
- Full parsing of SEC full-text submissions (HTML/XBRL/iXBRL) is
  non-trivial — different filers use different layouts, and robust extraction
  requires a purpose-built parser. Deferring this keeps the first version
  shippable while providing real metadata and deterministic section stubs that
  the agent can reason over. Section text can be upgraded to real parsed content
  independently without touching the tool or service layer.
- The deterministic fallback returns realistic section text templated for
  well-known tickers (NVDA, MSFT, AAPL, TSM, AMD) and generic stubs for
  others, so dev/test/demo environments never require network access.
- The keyword heuristic in `gather_node` triggers `sec_filings` when the
  message contains SEC/filing keywords (10-K, 10-Q, "risk factors", "annual
  report", etc.) OR when intent is research/trade_idea and a ticker is present.
  This covers both explicit filing queries and implicit fundamental lookups.

**Why full parsing is deferred.**
- SEC filings are delivered as HTM/HTML documents within ZIP archives or as
  inline XBRL. A robust parser must handle multiple document structures,
  identify section boundaries, and strip boilerplate — this is a significant
  engineering effort best delivered as a dedicated ingestion pipeline feeding
  Qdrant (the existing RAG store), not a synchronous tool call.
- The first version already delivers value: real filing dates and URLs, plus
  deterministic section stubs. The upgrade path is clear: a background ingestion
  job parses full-text filings and stores chunks in Qdrant; the agent then
  retrieves them via the existing `rag_retrieve` tool.

**Alternatives.** SEC-API.io (paid, good parsing), Polygon.io SEC filings
(paid), direct S3 EDGAR full-text index parsing (complex, high volume),
yfinance `get_financials` (limited coverage, no risk-factor text).

## ADR-012: In-process usage tracking for LLM and tool calls

**Decision.** Track LLM token usage, estimated cost, and tool invocations in
an in-memory `UsageService` that is wired into `LLMService` and `ToolRegistry`
via optional injection.  Expose the data through `GET /usage/events` and
`GET /usage/summary`.

**Why.**
- Transparency: operators and reviewers can see how many LLM calls were made,
  how many tokens were consumed, and which tools were invoked per session.
  This is essential for understanding agent behaviour during evaluation.
- Cost control: estimated USD cost is computed from approximate list-price
  constants at the point of each call, giving an early signal before a real
  billing integration is added.
- Foundation for plan limits: once usage is tracked, enforcing per-user or
  per-plan token/call budgets is a straightforward addition on top of this
  data — no schema migration needed.
- Non-invasive injection: `LLMService` and `ToolRegistry` accept an optional
  `usage_service` argument; when `None` (the default for all existing test
  code) they behave exactly as before.  No existing call site needed to change.
- In-memory first: the `UsageService` interface is designed so the backing
  store can be swapped to Postgres (or any persistent store) later.  The
  `list_usage_events()` / `get_usage_summary()` methods will keep the same
  contract; only the constructor and `_events` storage change.

**Cost constants.** Approximate OpenAI list prices as of early 2026.  They
are stored in one place (`usage_service.py`) and are clearly labelled as
estimates.  They are not used for billing.

**Alternatives.** LangSmith / LangFuse (third-party observability — adds
vendor dependency and data-egress risk); OpenTelemetry (flexible but
heavyweight for a first pass); manual logging (hard to aggregate and query).

## ADR-013: Optional LangSmith observability for LLM and agent tracing

**Decision.** Integrate LangSmith as an *optional* observability layer behind
three environment variables: `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, and
`LANGCHAIN_PROJECT`.  When tracing is disabled (the default), the entire
integration is a no-op with zero runtime overhead.

**Why.**
- Production debugging and evaluation of LLM-backed systems requires trace
  visibility at three levels: individual LLM calls, agent node transitions, and
  tool invocations.  Logs alone cannot reconstruct the causal chain across an
  async, multi-step graph.
- LangSmith is already a natural fit because the stack already depends on
  `langchain-core` and `langgraph`; adding the `langsmith` SDK does not
  introduce a framework change, only a new optional package.
- Making it optional is non-negotiable: tests, local development without an
  internet connection, and environments without a LangSmith plan must all work
  identically.  The guard `Settings.langsmith_enabled` and the `_tracing_active`
  sentinel ensure this at the module boundary.
- The `langsmith` package is added to an `[observability]` extras group so it
  is never pulled in transitively.  Production deployments that want tracing
  install `alphalens[observability]`; CI does not.

**Architecture.**
- `core/config.py` — three new fields: `LANGCHAIN_TRACING_V2` (bool, default
  `false`), `LANGCHAIN_API_KEY` (optional string), `LANGCHAIN_PROJECT`
  (string, default `"AlphaLens AI"`).  A `langsmith_enabled` property gates
  all downstream behaviour.
- `infrastructure/observability/langsmith.py` — single module with four
  public symbols:
  - `setup_langsmith(settings)` — called once at app startup; sets the three
    env vars LangSmith reads at import time and flips `_tracing_active`.
  - `trace_llm_call(name, *, metadata)` — context manager wrapping a single
    LLM operation (e.g. `classify_intent`, `synthesize_decision`).
  - `trace_node(node_name, *, inputs, metadata)` — context manager wrapping a
    LangGraph node execution.
  - `trace_tool_call(tool_name, inputs, metadata)` — fire-and-forget helper
    that annotates the current run tree with a tool invocation event.
  All four functions catch every exception internally; tracing can never crash
  the agent.
- `services/llm_service.py` — `classify_intent` and `synthesize_decision` are
  wrapped in `trace_llm_call` with `conversation_id` and `intent` as metadata.
- `agents/nodes.py` — `interpret`, `gather`, `synthesize`, and `decide` nodes
  are each wrapped in `trace_node`.  Tool calls inside `gather` record their
  name and kwargs via `trace_tool_call`.
- `api/main.py` — `create_app` calls `setup_langsmith(settings)` immediately
  after `configure_logging`.

**Metadata attached per trace.**
- `conversation_id` (available in state and service context)
- `input` / user message text (on `classify_intent` span)
- `intent` (on `synthesize_decision`, node, and tool spans)
- `tickers` (on gather, synthesize, decide spans)
- `node` name and `inputs` snapshot (on all node spans)
- `tool_call.name` and `tool_call.inputs` (on tool events)

**Fallback behaviour.** When `langsmith_enabled` is false, all wrappers yield
immediately.  When the `langsmith` package is not installed and `_tracing_active`
is somehow true (e.g. misconfigured), the `ImportError` is caught silently and
the wrapped body still executes.  In both cases the agent behaves identically to
the pre-tracing implementation.

**Test strategy.** `tests/test_observability.py` verifies:
- Config defaults: tracing is off, no API key required.
- `langsmith_enabled` gate: only true when both flag and key are present.
- `setup_langsmith` is a no-op unless both conditions hold.
- All tracing wrappers execute their body regardless of tracing state.
- Wrappers survive a simulated `ImportError` for the `langsmith` package.
- The full agent node pipeline (interpret → synthesize → decide) completes
  without error when tracing is disabled.

**Alternatives.**
- LangFuse: good open-source alternative; does not integrate as naturally with
  `langchain-core` / `langgraph` run trees.  Can be added alongside LangSmith.
- OpenTelemetry: vendor-neutral but requires an OTLP collector, a heavier
  instrumentation API, and does not natively understand LLM concepts (tokens,
  prompts, chain steps).
- Structured logging only: already in place via `structlog`; suitable for
  operational metrics but insufficient for LLM evaluation and replay.

## ADR-014: Service-layer caching with Redis (in-memory fallback)

**Decision.** Cache repeated external/expensive read operations at the
**service layer** behind a single `CacheService` facade.  Use Redis when
`CACHE_ENABLED=true` and `REDIS_URL` is set; otherwise (and on Redis failure)
use a thread-safe in-memory backend.  TTL defaults to `CACHE_TTL_SECONDS=300`.

**Why service layer (and not tools or integrations).**
- Services already own provider selection (primary vs deterministic fallback)
  and response normalisation into Pydantic schemas.  Caching at this boundary
  means we cache the *normalised, already-serialisable* shape — no transport
  artefacts leak into the cache key.
- Tools are thin orchestration wrappers; caching there would require each tool
  to know about the cache.  Integrations are transport adapters; caching their
  raw payloads would couple us to provider-specific shapes and break when we
  swap a provider.
- Service-layer caching is also opt-in by injection: every service accepts
  `cache: CacheService | None = None`, so existing tests and any future caller
  can disable caching trivially.

**What is cached.**
| Service                             | Key parts                              | Notes                                |
|-------------------------------------|----------------------------------------|--------------------------------------|
| `MarketDataService.get_quote`       | `op=quote`, ticker (uppercased)        | `get_quotes` benefits per-ticker.    |
| `SearchService.search`              | normalised query, `k`                  | Query lower-cased and stripped.      |
| `MacroService.get_series`           | series id, limit                       | Per-series cache.                    |
| `MacroService.get_macro_snapshot`   | constant (`op=snapshot`)               | One key for the aggregate snapshot.  |
| `SECService.get_recent_filings`     | ticker, sorted form types, limit       | Form types canonicalised.            |
| `SECService.get_filing_sections`    | ticker, form type                      | Most expensive call; biggest gain.   |
| `RAGService.get_relevant_context`   | normalised query, `k`, collection name | Cached as plain dicts; rehydrated.   |

**What is *not* cached** (intentionally).
- `ApprovalsService` — write-side state machine, must always reflect the
  authoritative store.
- `UsageService` — append-only telemetry; reads must be exact.
- `LLMService` — non-deterministic outputs; caching would mask drift and break
  the deterministic-fallback contract.  Tracing (ADR-013) covers visibility.
- `PortfolioService` — backed by an in-process loader; latency is already low
  and the data is mutable in tests.
- Tool registry calls themselves — caching happens *inside* the underlying
  service, so tools see the cached value automatically.

**Key construction.** `build_cache_key(namespace, payload)` JSON-serialises
the payload with `sort_keys=True` and SHA-256 hashes it.  Final key shape:
`alphalens:{namespace}:{hex-digest}`.  Equal payloads — regardless of dict
ordering — collapse to the same key.

**TTL strategy.** A single global `CACHE_TTL_SECONDS` (default 300) is used
for all namespaces.  This is intentionally simple; per-namespace TTLs can be
added later by accepting a `ttl_seconds` argument at the `set_cached` call
site (already supported by the API).  Five minutes is short enough that
quote staleness is bounded for users, long enough to absorb retries and
LangGraph re-executions within a single chat turn.

**Failure isolation.** Any cache exception — Redis disconnect, JSON
decode error, schema mismatch, missing key field — is caught at the
`CacheService` boundary, logged at `WARNING`, and the call proceeds against
the underlying provider.  At startup, if Redis is configured but unreachable,
`build_cache_backend` swaps to the in-memory backend silently.  The agent
behaviour is therefore identical whether Redis is up, down, or absent.

**Schemas remain unchanged.**  Marking responses with `cache_hit=true` would
require widening every cached response schema (most are `frozen=True`).  We
opted instead to surface cache hits through:
- `structlog`: a `cache_hit` event with the namespace, on every hit.
- `UsageService`: an opt-in `cache_hit` event type (added to `EventType`),
  visible at `GET /usage/events` when the usage service is wired into the
  cache facade.
This keeps the public response surface stable and the new dependency
purely additive.

**Alternatives considered.**
- Caching at the integration/transport layer: rejected — couples the cache
  to provider-specific shapes and prevents reuse across providers.
- Caching inside the FastAPI router via response middleware: rejected — would
  cache the entire `/agent/chat` decision, which depends on non-deterministic
  LLM output and approval state.  Service-level caching of *external* reads
  is the right granularity.
- A bespoke async client (e.g. `aioredis`): the synchronous `redis-py`
  client matches the synchronous shape of `MarketDataService` and friends and
  avoids introducing async/sync bridges in the call path.

## ADR-015: Short-lived conversation memory with simple LangGraph checkpointing

**Decision.** Add an optional conversation-memory layer behind a `MemoryService`
facade plus process-local LangGraph checkpointing keyed by `conversation_id`.
Memory is enabled by default (`MEMORY_ENABLED=true`), stores recent messages plus
lightweight per-turn metadata, and uses one of two backends:
- `MEMORY_BACKEND=in_memory` (default): thread-safe process-local store with TTL
- `MEMORY_BACKEND=redis`: Redis-backed store using `REDIS_URL`, with automatic
  in-memory fallback whenever Redis is unavailable

TTL defaults to `MEMORY_TTL_SECONDS=3600` (one hour).

**What is stored.**
- `messages`: alternating user / assistant turns, each as a small dict with
  `role`, `content`, and optional `metadata`
- `metadata`: one record per completed turn with fields such as `intent`,
  `recommendation`, `used_tools`, and the serialized `decision`

This is intentionally *not* full long-term memory. The MVP keeps only enough
recent state to support follow-up questions and simple debugging.

**Why this scope.**
- Multi-turn support is the immediate need: follow-up questions like "what about
  tomorrow?" should inherit the ticker / topic context from the previous turn.
- Storing only messages + small metadata keeps the model understandable,
  serializable, and easy to swap to a durable store later.
- Persisting raw tool payloads, token streams, or full LangGraph internals would
  increase storage volume and coupling without clear near-term value.

**How it is used at runtime.**
- `ChatService.chat()` always returns a `conversation_id` (existing behavior).
- When the caller supplies an existing `conversation_id`, `ChatService` loads a
  recent memory window and prepends it to the current request messages before
  invoking the graph.
- After a successful response, `ChatService` saves the latest user message, the
  assistant message, and a compact metadata record via `MemoryService.save_turn`.
- `GET /memory/{conversation_id}` returns the stored messages + metadata.
- `DELETE /memory/{conversation_id}` clears that conversation.

**LangGraph checkpointing.** The graph is compiled with a simple in-process
`MemorySaver` checkpointer when memory is enabled, and each invocation passes
`thread_id=conversation_id`.  This gives us stateful thread-scoped checkpoints
inside the running process at effectively zero complexity.  The user-facing
conversation memory is still managed by `MemoryService`; checkpoints are a
runtime convenience, not the source of truth.

**Why the checkpointing is intentionally simple.**
- LangGraph's in-memory checkpointer is sufficient for the MVP and aligns with
  the current single-process deployment model.
- A production-grade durable LangGraph checkpoint store would require an
  additional persistence design (schema, migration, recovery semantics), which
  is explicitly deferred for now.
- Conversation memory already provides the cross-call continuity users need.
  The checkpointer mainly improves future extensibility and preserves parity
  with the existing `conversation_id` thread model.

**Failure isolation.**
- If memory is disabled, `MemoryService` becomes a no-op and the app behaves as
  it does today.
- If Redis memory cannot connect or a Redis operation fails, the store logs a
  warning and degrades to an internal `InMemoryMemoryStore`.
- Memory failures never block `/agent/chat`.

**What is intentionally deferred.**
- Postgres-backed durable memory / checkpoint persistence
- Summarization or semantic compression of long conversations
- Retrieval-augmented long-term memory across sessions
- Per-user memory scoping and access control

The clear upgrade path is to keep the `MemoryService` API stable and swap its
store implementation to Postgres later, while leaving `ChatService` and the
API surface unchanged.

## ADR-016: Repository-based durable persistence for approvals

**Decision.** Move approval persistence to a repository abstraction with two
implementations:
- `InMemoryApprovalRepository` for local dev and tests (default)
- `SqlAlchemyApprovalRepository` for production databases

Select repository via configuration:
- `PERSISTENCE_BACKEND=in_memory` -> in-memory repository
- `PERSISTENCE_BACKEND=postgres` + `APP_DATABASE_URL` set -> SQLAlchemy/Postgres

**Why approvals first.**
- Approvals are mutable workflow records with explicit human decisions and
  reviewer notes, so durability matters more than ephemeral telemetry.
- The approval lifecycle (`pending` -> `approved/rejected/...`) is already
  centralized in `ApprovalsService`, which makes repository extraction low-risk.
- Persisting approvals unlocks auditability without forcing a full data-model
  migration for unrelated subsystems.

**Architecture.**
- `infrastructure/database.py` provides SQLAlchemy 2.0 primitives:
  `Base`, `create_engine_from_settings`, `get_session_factory`.
- `infrastructure/models.py` defines `ApprovalRecordModel` as the first ORM
  entity (including JSON evidence payload and reviewer decision fields).
- `repositories/approvals.py` contains:
  - `ApprovalRepository` protocol
  - in-memory implementation
  - SQLAlchemy implementation
- `ApprovalsService` now depends on `ApprovalRepository` and keeps its public
  API unchanged (`create_approval_from_decision`, `list_approvals`,
  `get_approval`, `decide_approval`).

**Startup behavior.** When `PERSISTENCE_BACKEND=postgres` and
`APP_DATABASE_URL` is present, tables are created on startup with
`Base.metadata.create_all(...)`. This is explicitly temporary bootstrapping.

**Why Alembic is deferred.**
- We add `alembic` dependency now and keep ORM/table structure migration-ready.
- The immediate requirement is durable approvals with minimal operational
  overhead; runtime `create_all` satisfies that for the first iteration.
- Once schema evolution becomes likely (new approval attributes, indexes,
  relationships), we will switch to explicit Alembic migrations and remove
  startup `create_all`.

**Scope boundaries.**
- `UsageService` remains in-memory and non-persistent for now.
- No auth/ownership model is added yet, so repository access remains
  application-internal only.
- No frontend changes are required; existing approvals API remains compatible.

## ADR-017: Optional speech transcription and lightweight multilingual chat

**Decision.** Add an optional speech-to-text layer behind a `SpeechClient`
protocol and a lightweight language-detection heuristic for the chat flow.
Speech is enabled by default (`SPEECH_ENABLED=true`), while response language
defaults to `auto` so the system mirrors the latest user message when possible.

**Why.**
- Speech support should be additive and safe: when OpenAI is configured we use
  it for transcription, otherwise the fallback returns a clear error or a mock
  result in tests.
- The MVP multilingual requirement does not justify a heavy translation stack.
  A simple heuristic for German, French, Arabic, and English is enough to route
  the response language metadata and keep the implementation deterministic.
- Keeping the language decision in the service layer means the chat agent can
  stay focused on reasoning and tools, while the UI only needs to upload audio
  and send the transcript into the existing chat endpoint.

**Scope boundaries.**
- Browser recording is deferred; the first version uses file upload.
- Full translation is deferred; deterministic answers keep the detected language
  in metadata and the agent can be upgraded later to synthesize fully localized
  responses.

