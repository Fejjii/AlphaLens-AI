# Security and Compliance

This document summarizes current security controls and compliance-oriented guardrails in AlphaLens AI.

## 1) Authentication

AlphaLens uses authenticated user flows for protected product surfaces and API routes.

## 2) JWT Access Tokens

Access tokens are used for authenticated API requests and route protection.

## 3) Refresh Token Revocation

Refresh token records support session continuity and revocation workflows.

## 4) Protected Routes

Sensitive APIs and frontend pages are protected by auth checks and user-scoped access.

## 5) Plan Quotas

Plan-aware quotas constrain usage and protect shared resources while exposing transparent usage status in UI.

## 6) Rate Limiting

Rate limiting is applied to relevant API paths with Redis-backed options for distributed enforcement.

## 7) Upload Validation

Knowledge uploads are validated before ingestion to reduce malformed content and unsafe file handling risks.

## 8) CORS and Security Headers

CORS is explicitly configured for known frontend origins; security headers and middleware controls are included at API boundary level.

## 9) Secret Handling

Secrets are environment-managed and should never be committed. `.env` remains ignored and untracked.

## 10) No Real Broker Execution

AlphaLens does not place trades or connect to broker execution in current scope.

## 11) HITL Approval Requirements

High-risk recommendations or weak-evidence outcomes can require human approval before operational acceptance.

## 12) Sensitive Actions Requiring Elevated Governance

- buy
- sell
- trim
- rebalance
- escalation
- high risk
- weak evidence

## 13) Disclaimers and Limitations

- This platform is not financial advice.
- Demo data can be synthetic unless real providers are configured.
- Recommendations are decision support artifacts, not autonomous execution instructions.

## 14) Compliance Metadata in Responses

Agent responses include structured compliance fields (e.g., policy flags, approval required indicators, and limitation notes) to support auditability.

## 15) What Remains for Real Production

- audit immutability
- policy versioning
- legal review
- role based access control
- 2FA
- password reset
- email verification
- stricter CSP
- Sentry
- container scanning
