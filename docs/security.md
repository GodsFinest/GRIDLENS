# Security model

## Authentication and authorization

Production mode reads API key mappings from `GRIDLENS_API_KEYS`. The server
derives the user and role from the key; request bodies cannot select a role.
In production, missing or invalid key configuration fails closed: an unconfigured
production API returns HTTP 503 (`services/safety/api_auth.py`).

| Role | Read | Investigate and validate | Submit simulated action | Approve simulated action |
| --- | :---: | :---: | :---: | :---: |
| `VIEWER` | Yes | No | No | No |
| `ENGINEER` | Yes | Yes | Yes | No |
| `APPROVER` | Yes | Yes | Yes | Yes |

An approver cannot approve an action submitted by the same username. Approval
tokens identify approved simulation records; no endpoint executes physical
control actions (`apps/api/routers/actions.py`, `services/safety/simulation_guard.py`).

## Input handling

Investigation queries and simulated-action justifications pass through
`InputSanitizer`. It is a boundary tripwire, not a complete filter: queries are
treated as data and never as instructions, while the deterministic evidence and
claim-verification path remains the primary defense
(`services/safety/sanitizer.py`).

COMTRADE identifiers are restricted before file resolution. CORS origins are
configured through the explicit `GRIDLENS_ALLOWED_ORIGINS` allowlist in
`apps/api/main.py`. Evaluation results use a one-hour in-memory cache to avoid
repeating the full benchmark on every request.

The web client deliberately reads its API key from `localStorage` rather than a
`NEXT_PUBLIC_*` bundle variable (`apps/web/lib/api.ts`). This keeps the key out
of the compiled configuration, but a browser-accessible localStorage key remains
exposable to XSS in a real deployment; production deployments need a stronger
credential-delivery and content-security policy design.

## Deployment boundary

The included authentication and state stores are suitable for local evaluation.
A deployment connected to operational systems would additionally require an
identity provider, persistent audit storage, managed secrets, request limits,
network isolation, and an independent safety review.
