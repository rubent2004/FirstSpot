# FirstSpot — Backend

FastAPI + SQLAlchemy async + PostGIS API. Alembic revision `0002_institutional_coordination` adds organization onboarding, verified members, invitations, and an append-only place activity log.

## Institution workflow

- `POST /api/v1/institutions/register`: creates a pending organization, owner account, and `FSP-…` tracking code. The code is not an identity credential.
- `POST /api/v1/institutions/verification`: moderator-only independent verification/rejection. Requires `X-Platform-Admin-Key` and the separately configured `PLATFORM_ADMIN_KEY`.
- `POST /api/v1/institutions/login`, `GET /api/v1/institutions/me`: individual account session/profile.
- `POST /api/v1/institutions/invites`: verified owner issues a one-use, expiring invite; only the digest is stored.
- `POST /api/v1/institutions/join`: redeem an invite and create a member account.
- `GET /api/v1/places/{place_id}/activities`: public place timeline. `POST` on the same route appends an action and requires a verified organization member.
- `PATCH /api/v1/places/{place_id}`: backward-compatible triage API; now authenticated and audited. Unauthenticated writes return 401; pending/rejected organizations receive 403.

Public responses include an individual display name and organization, never email/password data. Activity rows have no update/delete route, and PostgreSQL also rejects row mutation with an immutable-log trigger. The state update and its activity row commit in the same transaction.

## Secrets and local use

Copy `.env.example` to `.env`, then set both blank fields to independent random values of at least 32 characters. The blank template fails closed rather than shipping a predictable sample secret.

```bash
cp .env.example .env
openssl rand -hex 32 # use one result for JWT_SECRET
openssl rand -hex 32 # use a different result for PLATFORM_ADMIN_KEY
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

Never commit `.env`, expose the moderator key in browser code, or approve an organization solely because it knows its tracking code. Reviewers must independently check trusted public records/contact channels.

Before public production deployment, add/operate HTTPS, reverse-proxy rate limits for registration and login, monitoring/abuse response, secure backups, secret rotation, a recovery process, and privacy/retention policies. No patient-identifying data should be written to public activity notes. Email verification, password recovery, and distributed rate limiting are not implemented in this MVP.

OpenAPI source is regenerated from `app.main:export_openapi_schema` into `openapi.json`; the Vue SDK is regenerated from the root with `just codegen` or from `frontend/` with `pnpm generate:api`.
