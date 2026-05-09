# Evaluation

## 1) Backend Tests

Primary automated validation is the `pytest` suite. Latest full run in this repo state: `312 passed, 1 skipped, 6 warnings`.

Coverage focus includes:

- Router tests
- Router-to-tool wiring tests
- RAG tests
- Memo/report tests
- Investigation tests
- Auth tests
- Speech tests
- Approval tests

## 2) Frontend Validation

- `pnpm lint`
- `pnpm build`

## 3) Manual Acceptance Checklist

- Agent routing (`app_help`, `out_of_scope`, `clarification`, `investment_decision`)
- RAG policy responses and source trace
- SEC prompt behavior
- Macro prompt behavior
- Scenario prompt behavior
- Memo generation
- Investigations persistence
- Approvals workflow
- Feedback submission
- Auth persistence and expired token handling

## 4) Suggested Future Evaluation

- Golden prompt dataset for release gating
- Tool-selection accuracy scorecards
- RAGAS retrieval/evidence benchmarking
- LLM-as-judge rubric evaluations
- Faithfulness checks
- Citation quality scoring
- Feedback-driven evaluation loop
- LangSmith trace review workflow
