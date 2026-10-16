"""Response caching for LLM gateway calls."""

import hashlib
import json
from typing import Any


def make_cache_key(
    model_id: str,
    messages: list[dict[str, Any]],
    parameters: dict[str, Any],
) -> str:
    """Generate deterministic SHA-256 cache key from model and call arguments."""
    payload = {
        "model_id": model_id,
        "messages": messages,
        "parameters": parameters,
    }
    payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()


class ResponseCache:
    """In-memory cache for deterministic LLM responses with NO_CACHE bypass support."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, key: str, bypass_cache: bool = False) -> dict[str, Any] | None:
        if bypass_cache:
            return None
        return self._store.get(key)

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._store[key] = value

    def clear(self) -> None:
        self._store.clear()
