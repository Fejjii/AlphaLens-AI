# Limitations and Roadmap

## Immediate Limitations

- Demo/fallback data is still used in many flows
- Scenario simulation inside chat is first-order fallback style
- Knowledge base corpus is limited
- Document upload is currently manual and limited to `.md`/`.txt`
- Provider fallbacks can reduce external data fidelity
- No real trading/broker execution
- No full billing/admin surface yet
- Dev/test schema guard is used for report drift; production Alembic flow is pending
- Evaluation beyond tests/manual checks is still limited

## Roadmap

- Alembic production migration workflow
- Real portfolio import
- Broker and CSV import pipeline
- Register scenario simulator tool in agent registry
- Link `report_id` back to investigations more directly in UI workflows
- Admin dashboard
- Stripe billing integration
- Sentry + broader monitoring hardening
- LangSmith trace review workflow
- RAGAS and golden-set evaluation program
- Production frontend polish
- Real market data SLA and stronger reliability controls
- Stronger SEC parsing/extraction
- Auth hardening (2FA, verification, reset, session controls)
