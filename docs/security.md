# Security model

## Authentication and authorization

Production mode reads API key mappings from `GRIDLENS_API_KEYS`. The server
derives the user and role from the key; request bodies cannot select a role.

| Role | Read | Investigate and validate | Submit simulated action | Approve simulated action |
| --- | :---: | :---: | :---: | :---: |
| `VIEWER` | Yes | No | No | No |
| `ENGINEER` | Yes | Yes | Yes | No |
| `APPROVER` | Yes | Yes | Yes | Yes |

An approver cannot approve an action submitted by the same username. Approval
tokens identify approved simulation records; no endpoint executes physical
control actions.

## Input handling

Investigation queries and simulated-action justifications pass through
`InputSanitizer`. Detection is a request filter and audit signal, not the primary
trust boundary. Reports accept measurements and equipment facts only from typed
tool results and verified claims.

COMTRADE identifiers are restricted before file resolution. CORS origins are
configured through `GRIDLENS_ALLOWED_ORIGINS`. Evaluation results use a one-hour
in-memory cache to avoid repeating the full benchmark on every request.

## Deployment boundary

The included authentication and state stores are suitable for local evaluation.
A deployment connected to operational systems would additionally require an
identity provider, persistent audit storage, managed secrets, request limits,
network isolation, and an independent safety review.
