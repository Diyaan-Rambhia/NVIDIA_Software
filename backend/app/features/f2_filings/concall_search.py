"""Tavily-powered management concall and earnings press release discovery.

Per PROJECT.md §4.4, §5.10, and FR-F2-002..005.
Searches official exchange press releases, earnings conference call transcripts,
and management commentary via live search API, extracting structured claims
with verbatim quote character offsets for consistency auditing.
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Any
from urllib.error import HTTPError, URLError

from backend.app.config.env import Settings, load_settings
from backend.app.contracts.filings import Claim
from backend.app.features.f2_filings.commentary_extractor import (
    CommentaryItem,
    extract_commentary_items,
)

logger = logging.getLogger("backend.app.features.f2_filings.concall_search")

# In-memory cache for search results: (symbol, period) -> (text, primary_url)
_CONCALL_CACHE: dict[str, tuple[str, str | None]] = {}


def search_management_commentary(
    company_name: str,
    symbol: str,
    period: str,
    settings: Settings | None = None,
    max_results: int = 5,
) -> tuple[str, str | None]:
    """Search for management concall transcripts and earnings releases via Tavily."""
    cache_key = f"{symbol.strip().upper()}_{period.strip().upper()}"
    if cache_key in _CONCALL_CACHE:
        return _CONCALL_CACHE[cache_key]

    s = settings or load_settings()
    api_key = s.get_var_value("TAVILY_API_KEY")
    if not api_key:
        logger.info("TAVILY_API_KEY not configured; skipping live concall search")
        return ("", None)

    query = f"{company_name} {symbol} earnings call transcript press release management commentary {period}"
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "include_raw_content": False,
        "max_results": max_results,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            if not results:
                _CONCALL_CACHE[cache_key] = ("", None)
                return ("", None)

            # Combine content snippets from top search results
            snippets: list[str] = []
            primary_url = results[0].get("url")

            for res in results:
                content = (res.get("content") or "").strip()
                if content:
                    snippets.append(content)

            combined_text = "\n\n".join(snippets)
            _CONCALL_CACHE[cache_key] = (combined_text, primary_url)
            return (combined_text, primary_url)
    except HTTPError as exc:
        logger.warning("Tavily search HTTP error %d: %s", exc.code, exc.reason)
        return ("", None)
    except URLError as exc:
        logger.warning("Tavily search connection failed: %s", exc.reason)
        return ("", None)
    except Exception as exc:
        logger.warning("Failed to retrieve management commentary via Tavily: %s", exc)
        return ("", None)


def build_claims_from_text(
    source_text: str,
    company: str,
    symbol: str,
    period: str,
) -> list[tuple[Claim, CommentaryItem]]:
    """Extract structured claims from concall / earnings release text."""
    items = extract_commentary_items(source_text)
    results: list[tuple[Claim, CommentaryItem]] = []

    for item in items:
        # Normalize metric to standard rule taxonomy
        raw_m = (item.target_metric or "").lower()
        q_lower = item.quote.lower()

        if "margin" in raw_m or item.section == "margin_commentary" or "margin" in q_lower:
            metric_name = "operating margin"
            if any(w in q_lower for w in ["expanded", "expansion", "improved", "up", "higher"]):
                descriptor = "margin expansion"
            else:
                descriptor = "strong" if item.tone == "optimistic" else "cautious"
        elif any(w in q_lower for w in ["accelerat", "sequentially", "momentum", "picked up"]):
            metric_name = "revenue"
            descriptor = "accelerating"
        elif any(w in q_lower for w in ["headwind", "pressure", "uncertainty", "furloughs"]) or item.tone == "cautious":
            metric_name = "revenue"
            descriptor = "headwinds"
        elif "revenue" in raw_m or item.section in ("guidance", "revenue_commentary") or "revenue" in q_lower:
            metric_name = "revenue"
            descriptor = "strong" if item.tone == "optimistic" else "strong"
        else:
            metric_name = item.target_metric or "revenue"
            descriptor = "strong" if item.tone == "optimistic" else "cautious"

        direction = "declined" if any(w in q_lower for w in ["decline", "fell", "drop", "contracted"]) else "grew"

        claim = Claim(
            metric=metric_name,
            descriptor=descriptor,
            direction=direction,
            quote=item.quote,
            start=item.start,
            end=item.end,
            period=period,
            basis="reported",
        )
        results.append((claim, item))

    return results
