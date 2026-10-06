"""Groq LLM client with free model fallback chain.

Tries each free model in order. If one hits rate limits or fails, moves to the
next. All models in the chain are free-tier on Groq as of 2026.

The assistant never invents data — it only phrases facts from platform computations.
"""

from __future__ import annotations

from typing import Optional

import httpx

from pokequant.core.logging import get_logger

logger = get_logger(__name__)

# Groq models accessible on free/developer tiers (ordered fastest -> most capable).
# NOTE: Groq retires models periodically. As of late 2026 the llama-3.x models
# moved to Enterprise-only; the openai gpt-oss + qwen models are the current
# developer-tier options. Verify at https://console.groq.com/docs/models
FREE_MODELS = [
    "openai/gpt-oss-20b",    # 1000 T/s, cheapest — primary
    "openai/gpt-oss-120b",   # larger fallback
    "qwen/qwen3.8-27b",      # last-resort fallback
]

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqClient:
    """Groq chat completion client with automatic model fallback."""

    def __init__(self, api_key: str, models: Optional[list[str]] = None) -> None:
        self.api_key = api_key
        self.models = models or FREE_MODELS
        self.last_model_used: Optional[str] = None
        self._http = httpx.Client(timeout=30.0)

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> Optional[str]:
        """Send chat completion, trying each model in the fallback chain.

        Returns the response text, or None if all models are exhausted.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for model in self.models:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            try:
                resp = self._http.post(GROQ_API_URL, headers=headers, json=payload)

                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    self.last_model_used = model
                    logger.info("groq_success", model=model, tokens=data.get("usage", {}))
                    return content

                if resp.status_code == 429:
                    # Rate limited — try next model.
                    logger.warning("groq_rate_limited", model=model)
                    continue

                if resp.status_code in (400, 401, 403):
                    logger.error("groq_auth_error", model=model, status=resp.status_code)
                    return None  # Auth problem won't be fixed by switching models.

                # Other errors — try next model.
                logger.warning(
                    "groq_error", model=model, status=resp.status_code,
                    body=resp.text[:200],
                )
                continue

            except httpx.TimeoutException:
                logger.warning("groq_timeout", model=model)
                continue
            except Exception as exc:
                logger.warning("groq_exception", model=model, error=str(exc))
                continue

        logger.error("groq_all_models_exhausted")
        return None

    def close(self) -> None:
        self._http.close()
