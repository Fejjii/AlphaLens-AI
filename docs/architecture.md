# Architecture

AlphaLens AI is a full-stack agentic platform where frontend workflows call typed FastAPI endpoints, and investment decisions are orchestrated through LangGraph with tools, retrieval, governance, and durable records.

## A) System Architecture

```mermaid
flowchart LR
    FE[Frontend<br/>Next.js] --> API[Backend API<br/>FastAPI]
    API --> SVC[Services Layer]
    SVC --> AG[LangGraph Agent]
    AG --> TL[Tool Registry]
    TL --> PR[Providers]

    API --> PG[(Postgres)]
    API --> RD[(Redis)]
    TL --> QD[(Qdrant)]

    PR --> OA[OpenAI]
    PR --> SP[Serper]
    PR --> FR[FRED]
    PR --> AV[Alpha Vantage]
    PR --> SEC[SEC EDGAR]
```

## B) Agent Workflow

```mermaid
flowchart TD
    U[User message] --> R[Domain router]
    R --> AT{answer_type}
    AT -->|app_help| SC1[Short-circuit app help response]
    AT -->|out_of_scope| SC2[Short-circuit out-of-scope response]
    AT -->|clarification| SC3[Short-circuit clarification response]
    AT -->|investment_decision| I[interpret]
    I --> G[gather]
    G --> SY[synthesize]
    SY --> D[decide]
    D --> AP[approval flow]
    D --> IV[investigation record]
    D --> RP[report/memo workflow]
```

## C) Router to LangGraph Tool Wiring

```mermaid
flowchart TD
    DR[Domain router] --> ST[suggested_tools]
    ST --> GS[Graph state router_suggested_tools]
    GS --> GN[gather normalizes aliases]
    GN --> REG[Tool registry lookup]
    REG --> RUN[Execute available tools]
    REG --> SKIP[Skip unavailable tools]
    RUN --> TRACE[Trace: selected/executed]
    SKIP --> LIM[Limitations + skip reasons]
```

## D) Human Approval Workflow

```mermaid
flowchart TD
    DEC[Decision generated] --> GATE{Requires approval?}
    GATE -->|No| RET[Return answer]
    GATE -->|Yes| REC[Create approval record]
    REC --> UI[Approvals dashboard/page]
    UI --> ACT{Reviewer action}
    ACT -->|Approve| A1[approved]
    ACT -->|Reject| A2[rejected]
    ACT -->|More analysis| A3[needs_more_analysis]
```

## E) Investigation Workflow

```mermaid
flowchart TD
    ANS[Investment response] --> MK[Create investigation record]
    MK --> TL[Persist timeline entry]
    TL --> PAGE[Investigations page]
    PAGE --> LINK[Linked conversation, approval, and report context]
```

## F) Report and Memo Workflow

```mermaid
flowchart TD
    RESP[Agent response] --> MC[memo_context]
    MC --> RS[ReportService]
    RS --> SEC[Report sections]
    SEC --> RP[Reports page]
```

## G) Persistence Model

```mermaid
flowchart LR
    APP[Application runtime] --> PG[(Postgres<br/>durable entities)]
    APP --> RD[(Redis<br/>cache/rate-limit/memory option)]
    APP --> QD[(Qdrant<br/>vector retrieval)]
    APP --> MEM[(In-memory fallback<br/>demo/test)]
```

## Notes

- Router suggestions are first-class graph input and are merged with deterministic tool logic in `gather`.
- Tool orchestration trace tracks selected tools, executed tools, skipped tools, and limitations.
- Investigations and reports are persisted entities, not transient UI-only artifacts.
