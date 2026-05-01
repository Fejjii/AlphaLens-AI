# Architecture

AlphaLens AI is a production-minded, reviewer-first investment intelligence
platform. It combines typed APIs, explicit agent orchestration, deterministic
fallbacks, human approval gates, and deployment-ready infrastructure.

## 1) System Architecture

```mermaid
flowchart LR
    User[Reviewer / Analyst] --> FE[Frontend<br/>Next.js]
    FE -->|/api/backend proxy or direct API| BE[Backend API<br/>FastAPI]

    subgraph BackendRuntime[Backend Runtime]
        BE --> Agent[LangGraph agent]
        BE --> Services[Service layer]
        Agent --> Tools[Tool registry]
        Services --> RAG[RAG service]
        Services --> Integrations[Provider adapters]
        Services --> Repos[Repositories]
        Services --> AuthPlan[Auth + plans + quotas]
        Services --> Usage[Usage / feedback telemetry]
    end

    subgraph DataInfra[Data and infra]
        PG[(Postgres)]
        RD[(Redis)]
        QD[(Qdrant)]
    end

    subgraph External[External APIs]
        OA[OpenAI / LLM]
        AV[Alpha Vantage]
        SP[Serper]
        FR[FRED]
        SEC[SEC EDGAR]
    end

    Services --> PG
    Services --> RD
    RAG --> QD
    Integrations --> OA
    Integrations --> AV
    Integrations --> SP
    Integrations --> FR
    Integrations --> SEC

    subgraph Ops[Delivery]
        DK[Docker Compose]
        CI[GitHub Actions CI/CD]
    end
    DK --> FE
    DK --> BE
    CI --> FE
    CI --> BE
```

**Notes**
- Frontend is the reviewer UI and proxy entrypoint.
- Backend owns orchestration, tool invocation, provider routing, and persistence.
- Redis, Postgres, and Qdrant are first-class infra dependencies.
- External providers are optional; deterministic fallback behavior is preserved.

## 2) Agent Workflow

```mermaid
flowchart TD
    U[User message] --> I[Interpret intent]
    I --> G[Gather evidence]
    G --> T[Tool calls + RAG retrieval]
    T --> S[Synthesize]
    S --> D[Decide recommendation]
    D --> C[Compliance check]
    C --> A{Approval required?}
    A -->|Yes| AQ[Create approval request]
    A -->|No| R[Generate response]
    AQ --> R
    R --> O[Persist memory + usage events]
    O --> UI[Render chat + decision card]
```

**Steps**
- `interpret`: classify user intent and context.
- `gather`: retrieve portfolio/policy/market/news/macro/SEC/RAG evidence.
- `synthesize`: merge evidence into a coherent analysis.
- `decide`: produce typed recommendation, risk, confidence, and rationale.
- `compliance check`: attach policy flags, limitations, and approval reason.
- `approval gate`: create approval when risk/policy requires human review.
- `response generation`: return the answer plus decision metadata to frontend.

## 3) Tool and Provider Workflow

```mermaid
flowchart TD
    Agent[Agent node] --> Pick[Choose tool]
    Pick --> Tool[Tool registry function]
    Tool --> Service[Domain service]
    Service --> Provider{Real provider configured?}
    Provider -->|Yes| RealCall[Call external API]
    Provider -->|No| Fallback[Fallback provider]
    RealCall --> Normalize[Normalize typed payload]
    Fallback --> Normalize
    Normalize --> Track[Record usage/observability event]
    Track --> Return[Return tool result to agent]
```

**Behavior**
- Services hide provider-specific details from the agent and API layer.
- Fallback clients keep behavior deterministic when keys/network are unavailable.
- Usage events are recorded for LLM calls, tool calls, errors, cache hits, and
  generated artifacts.

## 4) RAG Workflow

```mermaid
flowchart TD
    KB[Internal markdown knowledge base] --> Chunk[Chunking / ingestion]
    Chunk --> Embed[Embeddings]
    Embed --> Index[Qdrant index]
    Query[User query] --> Retrieve[Retrieve top-k chunks]
    Retrieve --> Cite[Citations + evidence snippets]
    Cite --> Agent[Agent synthesis]
```

**Pipeline**
- Source docs live under `data/knowledge_base`.
- Markdown is ingested, chunked, embedded, and indexed in Qdrant.
- Retrieval returns evidence chunks used in chat/report reasoning and citations.

## 5) Human-in-the-Loop Workflow

```mermaid
flowchart TD
    Risky[Risky recommendation] --> Create[Create approval record]
    Create --> Queue[Approvals queue]
    Queue --> Reviewer[Reviewer action]
    Reviewer --> Approve[Approve]
    Reviewer --> Reject[Reject]
    Reviewer --> More[Needs more analysis]
    Approve --> Audit[Persist decision + note + timestamp]
    Reject --> Audit
    More --> Audit
    Audit --> State[Updated status visible in UI]
```

**Auditability**
- Approval records preserve recommendation, evidence, rationale, and decisions.
- Action trail is user-scoped and persistence-ready for production.

## 6) Auth and SaaS Workflow

```mermaid
flowchart TD
    Reg[Register] --> Login[Login]
    Login --> Access[Access token]
    Login --> Refresh[Refresh token]
    Access --> Guard[Protected routes and APIs]
    Guard --> Plan[Resolve user plan]
    Plan --> Quota[Quota checks]
    Quota --> Track[Usage tracking]
    Track --> BillingUX[Usage/cost and quota UI]
```

**Auth/SaaS controls**
- Auth endpoints issue bearer tokens and gate protected APIs.
- User plan metadata drives limits/capabilities and usage monitoring.
- Quota/usage status is surfaced in settings and usage dashboards.

## 7) Persistence Workflow

AlphaLens uses repository abstractions over SQLAlchemy-ready models while
preserving in-memory behavior for local/demo/test workflows.

**Persistence model**
- Repositories provide a stable contract to services.
- Postgres path is used in production-ready deployments (`APP_DATABASE_URL`,
  `PERSISTENCE_BACKEND=postgres`).
- In-memory fallback remains available for deterministic local/test runs.
- Data remains user-scoped at service/repository boundaries.

**Primary entities**
- users
- approvals
- feedback
- reports
- scenarios
- usage events
- conversation memory

## 8) Docker Workflow

```mermaid
flowchart LR
    FE[frontend container :3000] -->|/api/backend| BE[backend container :8000]
    BE --> PG[(postgres)]
    BE --> RD[(redis)]
    BE --> QD[(qdrant)]
    U[Browser] --> FE

    HC[Healthchecks] --> FE
    HC --> BE
    HC --> PG
    HC --> RD
    HC --> QD
```

**Container topology**
- `frontend` uses same-origin proxy routing to backend.
- `backend` serves API and agent workflow.
- `postgres`, `redis`, and `qdrant` provide infra dependencies.
- Healthchecks are defined for all services.
- Backend image includes repo `data/` to keep scenario/RAG runtime paths
  consistent inside Docker.

## Related Docs

- [README.md](../README.md)
- [setup.md](setup.md)
- [scripts.md](scripts.md)
- [codebase_guide.md](codebase_guide.md)
- [deployment.md](deployment.md)
- [demo_script.md](demo_script.md)
- [validation_report.md](validation_report.md)
