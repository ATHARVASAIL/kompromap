"""Optional API-key authentication.

The original spec scoped this as a single-user local tool with no auth
(§6), which is fine on localhost. It is *not* fine on a public URL: every
endpoint is otherwise fully open, and the data here is a map of a client's
vulnerabilities — arguably the most sensitive artifact a pentest produces.

So auth is opt-in rather than mandatory, to avoid breaking the local
workflow the tool was designed around:

  * API_KEY unset (default)  -> no auth, exactly as before. Intended for
                                localhost / docker-compose on your machine.
  * API_KEY set              -> every /api route except the health checks
                                requires `X-API-Key: <value>`.

The production compose file and DEPLOYMENT.md both push you toward setting
it. Health checks stay open deliberately so container/load-balancer probes
keep working without embedding a credential in the orchestrator config.
"""
import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency. No-op when no API_KEY is configured."""
    settings = get_settings()
    expected = settings.api_key

    if not expected:
        # Auth disabled — local/single-user mode.
        return

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Constant-time comparison: a plain `!=` leaks key material through
    # timing, since it short-circuits on the first differing byte.
    if not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
