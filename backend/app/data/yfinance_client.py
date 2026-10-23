"""Live yfinance market data client with server-side TTL caching.

Rules:
- Live retrieval at request time.
- Server cache with TTL and per-request limits from config.
- A failure returns a clear error with ticker names; never fill, never fall back to old data.
- Keeps label: 'unofficial source, delayed'.
- Never returns raw prices to external clients, only derived numbers.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
import yfinance as yf

logger = logging.getLogger("backend.app.data.yfinance_client")

# In-memory server cache: symbol -> (timestamp, {date_str: adj_close})
_YFINANCE_CACHE: dict[str, tuple[float, dict[str, float]]] = {}


def clean_ticker_symbol(symbol: str) -> str:
    """Ensure standard Yahoo ticker format for Indian equities and indices."""
    sym = symbol.strip()
    if sym in ("NSEI", "NIFTY", "NIFTY50", "^NSEI"):
        return "^NSEI"
    if sym in ("BSESN", "SENSEX", "^BSESN"):
        return "^BSESN"
    if sym.startswith("^"):
        return sym
    if not sym.endswith(".NS") and not sym.endswith(".BO"):
        return f"{sym}.NS"
    return sym


def fetch_live_ticker_history(
    symbol: str,
    cache_ttl_seconds: int = 3600,
) -> dict[str, float]:
    """Retrieve daily price history for a single ticker with TTL caching."""
    clean_sym = clean_ticker_symbol(symbol)
    now_ts = time.time()

    # Check cache
    if clean_sym in _YFINANCE_CACHE:
        cached_ts, cached_data = _YFINANCE_CACHE[clean_sym]
        if (now_ts - cached_ts) < cache_ttl_seconds:
            return cached_data

    # Live fetch at request time
    try:
        ticker = yf.Ticker(clean_sym)
        df = ticker.history(period="2y", auto_adjust=True)
        if df.empty or "Close" not in df.columns:
            raise ValueError(f"No price records returned for {clean_sym}")

        prices: dict[str, float] = {}
        for idx, row in df.iterrows():
            p = float(row["Close"])
            if np.isfinite(p) and p > 0:
                # Format index date
                d_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
                prices[d_str] = p

        if len(prices) < 20:
            raise ValueError(f"Insufficient historical prices ({len(prices)}) for {clean_sym}")

        # Store in cache
        _YFINANCE_CACHE[clean_sym] = (now_ts, prices)
        logger.info("Successfully fetched live yfinance data for %s (%d points)", clean_sym, len(prices))
        return prices

    except Exception as exc:
        logger.warning("yfinance fetch failed for %s: %s", clean_sym, exc)
        raise ValueError(
            f"Failed to fetch market data from yfinance for ticker '{symbol}' (unofficial source, delayed): {exc}"
        ) from exc


def fetch_universe_price_series(
    symbols: list[str],
    max_tickers: int = 100,
    cache_ttl_seconds: int = 3600,
) -> dict[str, dict[str, float]]:
    """Retrieve daily price history across a universe of tickers at request time."""
    if len(symbols) > max_tickers:
        raise ValueError(f"Ticker count ({len(symbols)}) exceeds configured limit of {max_tickers}")

    series_map: dict[str, dict[str, float]] = {}
    failed_tickers: list[str] = []

    for sym in symbols:
        try:
            series = fetch_live_ticker_history(sym, cache_ttl_seconds=cache_ttl_seconds)
            series_map[sym] = series
        except Exception:
            failed_tickers.append(sym)

    if failed_tickers:
        raise ValueError(
            f"Failed to fetch market data from yfinance for tickers: {sorted(failed_tickers)} "
            "(unofficial source, delayed). Incomplete market data cannot be processed."
        )

    return series_map
