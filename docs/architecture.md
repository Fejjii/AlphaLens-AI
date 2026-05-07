# Architecture

This document describes AlphaLens AI as a production-style agentic system with explicit orchestration, fallback providers, and human approval controls.

## A) System Architecture

```mermaid
flowchart LR
    U[User Browser]
    FE[Next.js Frontend]
    BE[FastAPI Backend]
    ORCH[Agent Orchestration<br/>LangGraph]
    TOOLS[Tool Layer]
    PROV[Provider Layer]

    PG[(Postgres)]
    RD[(Redis)]
    QD[(Qdrant)]

    OA[OpenAI]
    SP[Serper]
    FR[FRED]
    AV[Alpha Vantage]
    SEC[SEC EDGAR]

    U --> FE
    FE -->|/api/backend| BE
    BE --> ORCH
    ORCH --> TOOLS
    TOOLS --> PROV

    BE --> PG
    BE --> RD
    TOOLS --> QD

    PROV --> OA
    PROV --> SP
    PROV --> FR
    PROV --> AV
    PROV --> SEC
```

## B) Request Flow

```mermaid
flowchart TD
    Q[User question] --> FC[Frontend chat]
    FC --> API[/POST /agent/chat/]
    API --> LG[LangGraph workflow]
    LG --> TL[Tools]
    LG --> RAG[RAG retrieval]
    TL --> SYN[Synthesize decision response]
    RAG --> SYN
    SYN --> GATE{Approval gate required?}
    GATE -->|Yes| AQ[Create / update approval item]
    GATE -->|No| RESP[Return response payload]
    AQ --> RESP
    RESP --> RENDER[Frontend rendering]
```

## C) Provider Fallback Architecture

```mermaid
flowchart LR
    TOOL[Tool] --> ADAPTER[Provider adapter]
    ADAPTER --> CHECK{Real API configured and reachable?}
    CHECK -->|Yes| REAL[Real API path]
    CHECK -->|No| FALLBACK[Fallback path]
    REAL --> NORM[Structured response contract]
    FALLBACK --> NORM
    NORM --> RET[Return typed payload to agent]
```

## D) Human Approval Workflow

```mermaid
flowchart TD
    DEC[Agent decision] --> DETECT[Sensitive action detection]
    DETECT --> REQ{Approval required?}
    REQ -->|No| PASS[Return decision to user]
    REQ -->|Yes| QUEUE[Approval queue]

    QUEUE --> ACT{Reviewer action}
    ACT -->|Approve| APPR[approved]
    ACT -->|Reject| REJ[rejected]
    ACT -->|Needs more analysis| NMA[needs_more_analysis]

    APPR --> AUDIT[Audit trail]
    REJ --> AUDIT
    NMA --> AUDIT
```

## Notes

- Agent execution and tool/provider calls are separated so each layer can be validated independently.
- Structured responses ensure the UI can render recommendation, evidence, approval state, and limitations consistently.
- Fallback providers keep the product demoable when external keys are absent.
- Approval and audit flows enforce governance for high-risk or weak-evidence recommendations.
