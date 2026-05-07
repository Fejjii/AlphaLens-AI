# Data Architecture

This document explains what data AlphaLens AI manages, where it is stored, and what is sufficient for a demo versus a production SaaS implementation.

## 1) Data Domains in the App

1. Seeded synthetic portfolio holdings
2. Transactions
3. Watchlist
4. Cash
5. Internal knowledge base
   - Investment Policy
   - Risk Playbook
   - AI Infrastructure Thesis
   - Committee Notes
   - Readme
6. Uploaded user documents
7. Feedback
8. Reports
9. Scenarios
10. Approvals
11. Usage events
12. Conversation memory
13. Users and refresh tokens

## 2) Storage Architecture

### Postgres

Primary durable relational data:
- users
- refresh tokens
- approvals
- feedback
- reports
- scenarios
- usage events
- conversation memory

### Redis

Operational runtime support:
- cache responses and tool results where configured;
- rate limiting counters and policy;
- runtime memory fallback support where applicable.

### Qdrant

Retrieval and vector search:
- document vectors for internal and uploaded documents;
- chunk metadata (source, title/path, ingest timestamp, chunk index);
- retrieval collection (configured by `RAG_COLLECTION`, default collection pattern is `alphalens_knowledge` unless overridden).

### Local Files

Repository-seeded assets:
- synthetic portfolio and demo data under `data/`;
- seeded knowledge base markdown documents under `data/knowledge_base/`.

## 3) Demo Sufficiency

For portfolio-style demos and reviewer evaluation, the current dataset is enough to show:
- agent reasoning over portfolio + policy + retrieval evidence;
- approval routing and audit status transitions;
- report and scenario generation workflows;
- usage, feedback, and fallback provider observability.

## 4) What To Add for Professional SaaS

Recommended production data expansion:
- real portfolio import;
- broker integrations;
- market data history;
- benchmark data;
- risk factor data;
- company fundamentals;
- earnings transcripts;
- filing parser;
- audit snapshots;
- data freshness tracking;
- data quality checks.

## 5) Design Principles

- Keep data ownership explicit per bounded context (auth, approvals, reports, usage, RAG).
- Store decision-critical metadata in structured form, not only text blobs.
- Separate operational caches (Redis) from system-of-record persistence (Postgres).
- Treat retrieval corpora and vector indexes as first-class, versioned assets.
