# Limitations and Roadmap

## 1) Current Demo Limitations

- Some workflows rely on synthetic seeded data.
- Fallback providers are intentionally used in local/demo mode.
- End-to-end broker execution is intentionally out of scope.

## 2) AI Limitations

- Model outputs can still be uncertain or incomplete.
- Tool orchestration quality depends on prompt/routing coverage.
- Confidence signals are heuristic and require human oversight.

## 3) Data Limitations

- No full historical market/fundamentals warehouse yet.
- Portfolio import is not yet integrated with real custodians/brokers.
- Data freshness and quality checks are not fully automated.

## 4) RAG Limitations

- Retrieval quality depends on corpus and chunking.
- Citation granularity may be coarse.
- Enterprise-grade document permissions are not fully implemented.

## 5) Provider Limitations

- External APIs can be rate-limited or unavailable.
- Coverage varies across providers and regions.
- Some provider integrations are intentionally fallback-first for demos.

## 6) Compliance Limitations

- Approval flow exists, but immutable audit controls are still maturing.
- Policy governance/versioning needs stronger lifecycle management.
- Formal legal/compliance sign-off process is not embedded yet.

## 7) Deployment Limitations

- Production hardening is partial (security posture can be tightened).
- Full observability stack is not yet integrated in all environments.
- Scaling and high-availability patterns are not exhaustively validated.

## 8) Production Roadmap

- Alembic migrations
- Stripe billing
- admin dashboard
- real broker import
- real portfolio import
- document permissions
- observability with Sentry and LangSmith
- RAGAS evaluation
- hybrid search and reranking
- SEC parsing improvements
- fundamentals provider
- benchmark comparison
- PDF report export
- RBAC
- 2FA
- audit logging
- deployment hardening
