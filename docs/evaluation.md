# Evaluation and Quality Controls

## Current Validation Controls

1. Backend pytest suite
   - comprehensive test coverage over APIs, services, and agent behavior.
2. Agent routing regression tests
   - verifies intent/tool routing stability and orchestration behavior.
3. RAG retrieval tests
   - validates ingestion and retrieval expectations.
4. Speech tests
   - validates transcription pathway behavior and fallback handling.
5. Auth and quota tests
   - checks login/session controls and plan limit logic.
6. Repository and persistence tests
   - validates storage abstractions and persistence behavior.
7. Frontend lint
   - ensures TypeScript/React code quality baseline.
8. Frontend build
   - ensures production build integrity.
9. Docker validation
   - validates containerized build/runtime posture.
10. CI workflows
   - automated backend/frontend/docker/security checks via GitHub Actions.

## Recommended Future Evaluation Program

- RAGAS for retrieval quality benchmarking
- golden query set for deterministic regression checks
- LLM as judge evaluations with strict rubrics
- LangSmith trace review for orchestration diagnostics
- tool call accuracy metrics
- citation faithfulness checks
- response groundedness scoring
- portfolio calculation tests against known expected outputs
- scenario simulation validation with fixed fixtures
- red teaming for prompt injection
- load testing for API and workflow resilience

## Suggested Evaluation Cadence

- per PR: unit/integration + lint/build + security checks
- nightly: expanded regression set and deterministic prompt suites
- release gate: golden set pass, manual trace audit, smoke tests on deployed stack
