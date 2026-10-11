# NBros

NBros is a new Ithute Solutions product foundation for `https://nbro.ithute.co.ls/`.

This repository currently contains infrastructure and identity/realtime integration only. No fleet-management or other business module has been implemented yet; those will be designed from the project description.

## Foundation stack

- Next.js 16 + React 19 frontend
- FastAPI backend
- PostgreSQL owned exclusively by NBros
- Alembic database migrations
- Redis owned exclusively by NBros for product-local cache/coordination
- Central `!thute Auth` at `https://auth.ithute.co.ls`
- Central `!thute Realtime` at `wss://realtime.ithute.co.ls/v1/ws`

## Identity boundary

NBros never stores user passwords. Browser login uses OpenID Connect Authorization Code + PKCE (S256) with central `!thute Auth`, client/audience `nbros`, and callback:

`https://nbro.ithute.co.ls/api/auth/oidc/callback`

The initial NBros administrator enrollment gate is `justy@ithute.co.ls`. On the first valid central-authenticated request from that address, NBros creates a local product profile keyed by the immutable Auth `sub` UUID. The email is only an enrollment gate/snapshot; ongoing identity is the immutable central `sub`.

The administrator password belongs only in the running central Auth service or its runtime secret provisioning. It must never be added to this repository, NBros environment files, or the NBros database.

## Realtime boundary

NBros connects to the central Ithute realtime service rather than creating a separate WebSocket engine. A browser connects to `wss://realtime.ithute.co.ls/v1/ws` and sends its short-lived NBros central access token in the first WebSocket frame. NBros never reads the central realtime PostgreSQL or Redis data stores directly.

The Redis service in `compose.yaml` is product-local and separate from the Redis used by `!thute Realtime`.

## Optional standalone bootstrap admin login

The existing email/password form uses Ithute Central Auth by default. For **explicitly enabled local development only**, configure in the private `.env`:

```env
NBROS_BOOTSTRAP_LOGIN_ENABLED=true
NBROS_BOOTSTRAP_ADMIN_EMAIL=justy@ithute.co.ls
NBROS_BOOTSTRAP_ADMIN_PASSWORD=<unique-random-password-at-least-12-characters>
NBROS_BOOTSTRAP_SIGNING_SECRET=<independent-random-secret-at-least-32-characters>
```

Generate random secrets with `openssl rand -base64 36`; never commit secrets. Set `NBROS_PUBLIC_URL=http://localhost:3203`, `NBROS_OIDC_REDIRECT_URI=http://localhost:3203/api/auth/oidc/callback`, and `NBROS_COOKIE_SECURE=false` for localhost HTTP. Run `docker compose up --build -d`. The configured bootstrap account can use the normal login form without Ithute Auth. Bootstrap tokens expire after one hour and have no refresh token; normal users and SSO still use Central Auth. Bootstrap sign-in is rate limited and fails closed when Redis is unavailable. Disable bootstrap login when not needed.

## Local development

1. Copy `.env.example` to `.env`.
2. Set `NBROS_DB_PASSWORD` to a strong local value.
3. Start with `docker compose up --build`.
4. Frontend: `http://localhost:3203`
5. Backend: `http://localhost:8203`

Production ingress should use `deploy/Caddyfile.nbro` so `/api/v1/*`, `/healthz`, and `/readyz` reach FastAPI while all other routes reach Next.js.

## Central platform registration

The Ithute platform defaults/examples in this repository register `nbros` as a first-party Auth and Realtime client. Production runtime configuration must preserve these values when environment overrides are used:

- Auth client: `nbros:NBros`
- OIDC callback: `https://nbro.ithute.co.ls/api/auth/oidc/callback`
- Auth CORS origin: `https://nbro.ithute.co.ls`
- Realtime allowed user/service client: `nbros`

## Status

Foundation only. Awaiting the NBros project description before any business schema, workflow, screen, fleet entity, reporting feature, or operational rule is added.
