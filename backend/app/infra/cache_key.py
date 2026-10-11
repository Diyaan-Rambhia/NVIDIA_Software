"""Response-cache key generator per PROJECT.md §4.5 (FR-LLM-007) and PROGRESS.md A3.1."""

import hashlib
import json
from typing import Any


def canonical_json_dumps(obj: Any) -> str:
    """Serialize object to canonical JSON with sorted keys and compact separators."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def compute_cache_key(
    model: str,
    prompt: str,
    parameters: dict[str, Any],
    data_version: str,
) -> str:
    """Compute a deterministic SHA-256 response-cache key.

    Parameters
    ----------
    model : str
        Model identifier or alias (e.g. 'deep', 'fast', or concrete model ID).
    prompt : str
        The final prompt string as given without reformatting.
    parameters : dict[str, Any]
        Inference parameters (temperature, max_tokens, etc.). Parameter order
        does not change the resulting key due to canonical key sorting.
    data_version : str
        Version identifier of underlying data/context (e.g. filing digest, corpus hash).

    Returns
    -------
    str
        Hexadecimal SHA-256 digest of the canonical JSON payload.
    """
    payload = {
        "data_version": data_version,
        "model": model,
        "parameters": parameters,
        "prompt": prompt,
    }
    canonical_str = canonical_json_dumps(payload)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
