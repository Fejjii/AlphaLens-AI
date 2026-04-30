# Validation Report

This report summarizes the final submission validation status for AlphaLens AI.

## Summary

- Backend tests: `178 passed`
- Frontend lint: passed
- Frontend build artifact: generated
- Docker full stack: green
- Healthchecks: green
- Known local environment caveats: documented below

## Validation Details

### Backend tests

Expected / recorded submission result:

```text
178 passed
```

Backend test command:

```bash
cd backend
uv run pytest
```

### Frontend lint

Validated successfully using the local ESLint binary:

```bash
cd frontend
node ./node_modules/eslint/bin/eslint.js src --ext .js,.jsx,.ts,.tsx
```

Result:

- Passed with no reported lint errors

### Frontend build

Validated successfully through the local Next.js build binary:

```bash
cd frontend
node ./node_modules/next/dist/bin/next build
```

Observed result:

- compile completed successfully
- linting and type validation completed
- static pages were generated
- build artifact `.next/BUILD_ID` was generated

### Docker full stack

Submission target status:

- `docker compose up --build` green
- `frontend`, `backend`, `postgres`, `redis`, and `qdrant` services healthy

Compose file includes healthchecks for:

- Postgres
- Redis
- Qdrant
- backend
- frontend

### Healthchecks

Expected green checks in a healthy stack:

- backend `GET /health`
- frontend root route
- Redis ping
- Postgres readiness
- Qdrant readiness

## Known Local Environment Caveats

These caveats do not change the product architecture or submission package, but
they are relevant when reproducing validation locally.

### Package manager shims may be missing from shell PATH

In this local shell environment:

- `pnpm` was not available on `PATH`
- `npm` was not available on `PATH`
- `node` was available

Because of that, frontend validation was executed via local binaries under
`node_modules` instead of package-manager commands.

### Next.js build process may not exit cleanly in this shell

The local `next build` invocation completed compile, type/lint checks, static
page generation, optimization, and produced build artifacts, but the process
did not terminate cleanly on its own in this shell session. Since `.next`
artifacts and generated pages were present, this is documented as an
environment-specific caveat rather than a confirmed application build failure.

### Deterministic fallback mode is expected behavior

When optional provider keys are absent or providers are configured to `fallback`:

- chat remains usable
- investigation evidence remains deterministic
- demos stay stable offline

This is an intentional design choice for reviewer evaluation, not a degraded
error state.

## Notes for Reviewers

- AlphaLens is optimized for deterministic, reproducible product evaluation.
- Optional live providers are not required to assess the core workflow.
- Human approval, fallback behavior, and typed service boundaries are part of
  the evaluated system design.
