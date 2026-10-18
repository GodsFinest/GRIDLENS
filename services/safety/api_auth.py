"""API-key authentication for the local service.

Production deployments must configure GRIDLENS_API_KEYS as a comma-separated
list of key|username|role entries. Development remains convenient when no
keys are configured, but that mode is explicitly not production-safe.
"""
import os
from fastapi import Header, HTTPException
from services.safety.rbac import SecurityContext, UserRole


def _configured_keys() -> dict[str, SecurityContext]:
    entries = {}
    for raw in os.getenv("GRIDLENS_API_KEYS", "").split(","):
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) != 3:
            continue
        key, username, role_text = parts
        try:
            role = UserRole(role_text.upper())
        except ValueError:
            continue
        entries[key] = SecurityContext(
            user_id=username,
            username=username,
            role=role,
        )
    return entries


async def require_api_key(x_gridlens_api_key: str | None = Header(default=None)) -> SecurityContext:
    configured = _configured_keys()
    if configured:
        context = configured.get(x_gridlens_api_key or "")
        if context is None:
            raise HTTPException(status_code=401, detail="Valid GridLens API key required.")
        return context

    if os.getenv("GRIDLENS_ENV", "development").lower() == "production":
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured; production API is unavailable.",
        )

    return SecurityContext(user_id="local-dev", username="local-dev", role=UserRole.ENGINEER)
