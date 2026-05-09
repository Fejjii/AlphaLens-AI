# Security and Compliance

## 1) Authentication

- JWT access tokens protect authenticated API routes
- Refresh tokens support session continuity
- Logout/revocation flows invalidate refresh token sessions
- Expired access tokens return `401` with structured error payloads

## 2) Authorization

Repositories and API handlers are user-scoped so one user cannot access another user's:

- Conversations
- Reports
- Investigations
- Approvals

## 3) Rate Limiting

Rate limiting supports:

- In-memory backend (dev/test)
- Redis backend (shared/distributed runtime)

Limits are applied to key routes including auth, chat, speech, reports, scenarios, and feedback.

## 4) Upload Validation

Input validation exists for:

- Speech uploads (type/size checks, provider-mode handling)
- Knowledge document uploads (`.md`/`.txt` ingestion flow)

## 5) Financial Compliance Guardrails

- Platform includes explicit non-advisory framing
- No broker/trading execution
- Sensitive recommendation paths can require approval
- Weak evidence or tool limitations are surfaced in response metadata
- Human-in-the-loop remains central for higher-risk decisions

## 6) Secret Handling

- `.env` is ignored and should remain untracked
- Secrets are environment-managed
- Runtime/provider status endpoints expose modes/reasons, not secret values
- Logging should avoid raw secret leakage

## 7) Production Gaps

- Alembic-driven migration workflow
- Sentry/error monitoring integration
- Stronger audit logging and immutable trails
- Admin operations dashboard
- 2FA, email verification, password reset hardening
- Stricter CSP/CORS posture per environment
- Container/image scanning in release workflows
