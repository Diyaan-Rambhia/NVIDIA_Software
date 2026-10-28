"""Generate synthetic demo trade log using real market dates and prices.

Owner-approved exception to real-data policy recorded in DECISIONS.md.
All dates and prices are real historical closes from data/yfinance/.
Symbols come from config/universe.yaml.
"""

import csv
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.app.config.loader import load_config_file
from backend.app.config.models import ParametersConfig, UniverseConfig

PARAMETERS_PATH = _REPO_ROOT / "config" / "parameters.yaml"
UNIVERSE_PATH = _REPO_ROOT / "config" / "universe.yaml"
DATA_YFINANCE_DIR = _REPO_ROOT / "data" / "yfinance"
OUTPUT_DIR = _REPO_ROOT / "private" / "logs"
OUTPUT_FILE = OUTPUT_DIR / "demo_synthetic_log.csv"
SYNTHETIC_MARKER = "SYNTHETIC_DEMO"


def load_symbol_prices() -> dict[str, dict[str, float]]:
    """Load real dates and close prices for universe symbols from data/yfinance/."""
    universe_cfg = load_config_file(UNIVERSE_PATH, UniverseConfig)
    universe_symbols: set[str] = set()
    for sym_list in universe_cfg.sectors.values():
        universe_symbols.update(sym_list)

    symbol_prices: dict[str, dict[str, float]] = {}

    for sym in sorted(universe_symbols):
        cand = [
            DATA_YFINANCE_DIR / f"{sym}.json",
            DATA_YFINANCE_DIR / f"{sym}.NS.json",
        ]
        target: Path | None = None
        for p in cand:
            if p.is_file():
                target = p
                break

        if target is None:
            continue

        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            chart = raw.get("chart", {})
            results = chart.get("result", [])
            if not results:
                continue

            res = results[0]
            timestamps = res.get("timestamp", [])
            indicators = res.get("indicators", {})
            adjcloses = indicators.get("adjclose", [{}])[0].get("adjclose", [])

            if not timestamps or not adjcloses or len(timestamps) != len(adjcloses):
                continue

            prices: dict[str, float] = {}
            for ts, price in zip(timestamps, adjcloses, strict=True):
                if price is not None and np.isfinite(price) and price > 0:
                    d_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                    prices[d_str] = float(price)

            if len(prices) >= 30:
                symbol_prices[sym] = prices
        except Exception:
            continue

    return symbol_prices


def generate_synthetic_log(
    output_path: Path | None = None,
    num_trades: int | None = None,
    qty_min: float | None = None,
    qty_max: float | None = None,
    seed: int | None = None,
) -> Path:
    """Generate deterministic synthetic demo log using real historical prices."""
    params_cfg = load_config_file(PARAMETERS_PATH, ParametersConfig)

    trades_count = (
        num_trades
        if num_trades is not None
        else int(params_cfg.parameters["synthetic_log_trades"].default)
    )
    q_min = (
        qty_min
        if qty_min is not None
        else float(params_cfg.parameters["synthetic_log_qty_min"].default)
    )
    q_max = (
        qty_max
        if qty_max is not None
        else float(params_cfg.parameters["synthetic_log_qty_max"].default)
    )
    rand_seed = (
        seed
        if seed is not None
        else int(params_cfg.parameters["synthetic_log_seed"].default)
    )

    if output_path is None:
        output_path = OUTPUT_FILE

    rng = random.Random(rand_seed)
    sym_prices = load_symbol_prices()
    if not sym_prices:
        raise ValueError("No stored price series found in data/yfinance/ for universe symbols")

    # Load real benchmark index dates from stored data
    from backend.app.features.f3_log.pipeline import load_benchmark_price_history
    bm_prices = load_benchmark_price_history("NSEI")
    bm_dates = set(bm_prices.keys())

    # Find common real trading dates across available symbols and benchmark
    symbol_keys = sorted(sym_prices.keys())
    common_dates_set = set.intersection(
        bm_dates, *(set(sym_prices[s].keys()) for s in symbol_keys[:5])
    )
    if len(common_dates_set) < trades_count:
        # Fall back to dates present in at least one available symbol and benchmark
        all_dates = sorted(
            bm_dates.intersection(set.union(*(set(sym_prices[s].keys()) for s in symbol_keys)))
        )
    else:
        all_dates = sorted(common_dates_set)

    if len(all_dates) < trades_count:
        raise ValueError(
            f"Insufficient real trading dates ({len(all_dates)}) for {trades_count} trades"
        )

    # Sample dates in strictly chronological order
    chosen_date_indices = sorted(rng.sample(range(len(all_dates)), trades_count))
    chosen_dates = [all_dates[i] for i in chosen_date_indices]

    positions_held: dict[str, float] = {}
    rows: list[dict[str, str | float]] = []

    for d_str in chosen_dates:
        # If open positions exist and rng says SELL, execute a sell
        open_syms = [s for s, q in positions_held.items() if q > 0]
        if open_syms and rng.random() > 0.6:
            sym = rng.choice(open_syms)
            side = "SELL"
            max_sell = positions_held[sym]
            qty = round(rng.uniform(min(q_min, max_sell), max_sell), 2)
            positions_held[sym] -= qty
        else:
            sym = rng.choice(symbol_keys)
            side = "BUY"
            qty = round(rng.uniform(q_min, q_max), 2)
            positions_held[sym] = positions_held.get(sym, 0.0) + qty

        # Price must come strictly from real stored price on that date; missing raises
        if d_str not in sym_prices[sym]:
            raise ValueError(
                f"Missing price for symbol '{sym}' on trading date {d_str}; real price required"
            )

        real_price = sym_prices[sym][d_str]

        rows.append(
            {
                "Date": d_str,
                "Symbol": sym,
                "Side": side,
                "Quantity": qty,
                "Price": round(real_price, 2),
                "Marker": SYNTHETIC_MARKER,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        # Record seed in metadata comment header
        f.write(f"# synthetic_demo_seed: {rand_seed}\n")
        writer = csv.DictWriter(
            f,
            fieldnames=["Date", "Symbol", "Side", "Quantity", "Price", "Marker"],
        )
        writer.writeheader()
        writer.writerows(rows)

    return output_path


if __name__ == "__main__":
    out = generate_synthetic_log()
    print(f"Synthetic demo log written to {out}")
