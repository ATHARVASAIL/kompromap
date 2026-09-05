"""AI provider abstraction.

Kompromap previously called the Anthropic SDK directly from
`services/reporting.py`. That worked, but it hardcoded one vendor into a
service module and gave every future AI feature its own copy of the
timeout/retry/error handling. This is the seam.

Design rules this enforces:

* **The core app never imports a vendor SDK.** Only providers do.
* **Providers never raise.** Every call returns an `AIResult` carrying
  either text or a failure reason. An AI feature failing must degrade the
  product, never break it — the analyst still has the finding, the
  evidence, and their own judgement.
* **API keys stay server-side.** Nothing here is ever serialised to the
  frontend; `AIResult` deliberately carries no credential material.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AIFailure(str, Enum):
    """Why a call didn't produce usable output.

    Distinguished rather than collapsed into one error because the UI
    should say something different for each: "no key configured" is a
    setup step, "rate limited" is worth retrying, "provider error" is not
    the analyst's problem to fix.
    """

    NOT_CONFIGURED = "not_configured"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    PROVIDER_ERROR = "provider_error"
    EMPTY_RESPONSE = "empty_response"


@dataclass(frozen=True)
class AIResult:
    text: str | None
    failure: AIFailure | None = None
    model: str | None = None

    @property
    def ok(self) -> bool:
        return self.text is not None and self.failure is None

    @property
    def failure_message(self) -> str:
        """Analyst-facing explanation. Never leaks provider internals —
        a raw SDK traceback in the UI is noise at best and an information
        leak at worst."""
        return {
            AIFailure.NOT_CONFIGURED: (
                "No AI provider is configured. Set an API key to enable AI triage; "
                "everything else in Kompromap works without it."
            ),
            AIFailure.TIMEOUT: "The AI provider timed out. Try again.",
            AIFailure.RATE_LIMITED: "The AI provider is rate limiting. Try again shortly.",
            AIFailure.PROVIDER_ERROR: "The AI provider returned an error.",
            AIFailure.EMPTY_RESPONSE: "The AI provider returned nothing usable.",
        }.get(self.failure or AIFailure.PROVIDER_ERROR, "AI analysis is unavailable.")


class AIProvider(ABC):
    """A text-in/text-out model. Deliberately narrow: structured output,
    schema validation and prompt construction are the caller's job, so
    swapping vendors can't quietly change triage semantics."""

    name: str = "abstract"

    @abstractmethod
    def complete(self, system: str, user: str, *, max_tokens: int = 2000) -> AIResult:
        """Never raises. Returns AIResult with either text or a failure."""

    @property
    def is_configured(self) -> bool:
        return True


class NullProvider(AIProvider):
    """Used when no key is set. Exists so calling code has no `if provider
    is None` branches — an unconfigured install takes exactly the same
    path as a failed call, which is the path that's actually tested."""

    name = "none"

    @property
    def is_configured(self) -> bool:
        return False

    def complete(self, system: str, user: str, *, max_tokens: int = 2000) -> AIResult:
        return AIResult(text=None, failure=AIFailure.NOT_CONFIGURED)


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: float = 60.0, max_retries: int = 1):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries

    def complete(self, system: str, user: str, *, max_tokens: int = 2000) -> AIResult:
        try:
            import anthropic
        except ImportError:
            logger.warning("anthropic SDK not installed; AI features disabled")
            return AIResult(text=None, failure=AIFailure.NOT_CONFIGURED)

        try:
            client = anthropic.Anthropic(
                api_key=self._api_key, timeout=self._timeout, max_retries=self._max_retries
            )
            response = client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
            text = "\n".join(p for p in parts if p).strip()
            if not text:
                return AIResult(text=None, failure=AIFailure.EMPTY_RESPONSE, model=self._model)
            return AIResult(text=text, model=self._model)

        except Exception as exc:  # noqa: BLE001 — providers must never raise
            failure = _classify(exc)
            # Log the detail server-side; the analyst sees only the category.
            logger.warning("AI provider call failed (%s): %s", failure.value, exc)
            return AIResult(text=None, failure=failure, model=self._model)


def _classify(exc: Exception) -> AIFailure:
    """Map an SDK exception to a failure category by name rather than by
    importing vendor exception types — keeps this module free of a hard
    SDK dependency and tolerant of SDK version churn."""
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "timeout" in name or "timeout" in text:
        return AIFailure.TIMEOUT
    if "ratelimit" in name or "rate_limit" in text or "429" in text:
        return AIFailure.RATE_LIMITED
    return AIFailure.PROVIDER_ERROR


def get_provider() -> AIProvider:
    """Build the configured provider. Import-time-free so tests can patch
    settings without reloading modules."""
    from app.core.config import get_settings

    settings = get_settings()
    provider_name = (getattr(settings, "ai_provider", "anthropic") or "anthropic").lower()

    if provider_name in ("none", "off", "disabled"):
        return NullProvider()

    if provider_name == "anthropic":
        if not settings.anthropic_api_key:
            return NullProvider()
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            timeout=getattr(settings, "ai_timeout_seconds", 60.0),
            max_retries=getattr(settings, "ai_max_retries", 1),
        )

    logger.warning("Unknown AI provider %r; AI features disabled", provider_name)
    return NullProvider()
