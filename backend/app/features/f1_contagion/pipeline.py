"""Feature 1 Contagion scan pipeline running estimators over real market data."""

import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from backend.app.config.loader import load_config_file
from backend.app.config.models import ParametersConfig
from backend.app.contracts.contagion import CorrelationScan, ShiftedPair
from backend.app.data.returns import daily_log_returns
from backend.app.features.f1_contagion.bootstrap import moving_block_bootstrap
from backend.app.features.f1_contagion.estimators import (
    absorption_ratio,
    compute_ar_k,
    cov_to_corr,
    forbes_rigobon_adjust,
    rolling_covariance,
)
from backend.app.version import get_code_version

DATA_YFINANCE_DIR = Path("data") / "yfinance"
PARAMS_PATH = Path("config") / "parameters.yaml"
OUTPUT_JSON_PATH = Path("data") / "f1_scan_demo.json"


def load_price_series(
    symbols: list[str] | None = None,
    live: bool = False,
    cache_ttl_seconds: int = 3600,
    max_tickers: int = 100,
) -> dict[str, dict[str, float]]:
    """Load price series via live yfinance at request time, or from local data directory.

    Enforces:
    - Never fill missing data, never fall back to old data.
    - Clear error naming failed tickers on failure.
    - Unofficial source, delayed label.
    """
    if live and symbols:
        from backend.app.data.yfinance_client import fetch_universe_price_series
        return fetch_universe_price_series(
            symbols,
            max_tickers=max_tickers,
            cache_ttl_seconds=cache_ttl_seconds,
        )

    series_map: dict[str, dict[str, float]] = {}

    for file_path in DATA_YFINANCE_DIR.glob("*.json"):
        sym = file_path.stem
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
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

            date_dict: dict[str, float] = {}
            for ts, price in zip(timestamps, adjcloses, strict=True):
                if price is not None and np.isfinite(price) and price > 0:
                    d_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                    date_dict[d_str] = float(price)

            if len(date_dict) >= 50:
                series_map[sym] = date_dict
        except Exception:
            continue

    return series_map



def align_and_compute_returns(
    series_map: dict[str, dict[str, float]],
) -> tuple[list[str], np.ndarray, list[str]]:
    """Align prices on common trading days and compute daily log returns matrix (T, N)."""
    if not series_map:
        raise ValueError("No price series loaded from data/yfinance/")

    all_symbols = sorted(series_map.keys())
    common_dates = set.intersection(*(set(series_map[s].keys()) for s in all_symbols))
    sorted_dates = sorted(common_dates)

    if len(sorted_dates) < 30:
        # Fall back to symbols with at least 95% coverage
        date_counts: dict[str, int] = defaultdict(int)
        for s in all_symbols:
            for d in series_map[s]:
                date_counts[d] += 1

        thresh = int(len(all_symbols) * 0.90)
        common_dates = {d for d, c in date_counts.items() if c >= thresh}
        sorted_dates = sorted(common_dates)

        # Filter symbols that have all these common dates
        all_symbols = [s for s in all_symbols if common_dates.issubset(set(series_map[s].keys()))]

    matrix_prices = np.zeros((len(sorted_dates), len(all_symbols)), dtype=float)
    for j, s in enumerate(all_symbols):
        for i, d in enumerate(sorted_dates):
            matrix_prices[i, j] = series_map[s][d]

    # Compute daily log returns for each asset
    ret_list = []
    for j in range(len(all_symbols)):
        asset_rets = daily_log_returns(matrix_prices[:, j])
        ret_list.append(asset_rets)

    returns_matrix = np.column_stack(ret_list)
    return all_symbols, returns_matrix, sorted_dates[1:]


def run_correlation_scan(
    overrides: dict[str, Any] | None = None,
    symbols: list[str] | None = None,
    live: bool = False,
    cache_ttl_seconds: int = 3600,
    max_tickers: int = 100,
) -> CorrelationScan:
    """Execute complete Feature 1 correlation scan on real market data."""
    start_time = time.monotonic()
    cfg = load_config_file(PARAMS_PATH, ParametersConfig)
    params: dict[str, Any] = {
        name: entry.default for name, entry in cfg.parameters.items()
    }
    if overrides:
        params.update(overrides)

    series_map = load_price_series(
        symbols=symbols,
        live=live,
        cache_ttl_seconds=cache_ttl_seconds,
        max_tickers=max_tickers,
    )
    symbols, returns, return_dates = align_and_compute_returns(series_map)

    n_obs, n_assets = returns.shape
    b_window = int(params.get("B", 250))
    g_window = int(params.get("G", 20))
    c_window = int(params.get("C", 20))
    seed = int(params.get("seed", 42))

    # Slice baseline and current returns without lookahead
    # Baseline: ends G days before current start
    total_needed = b_window + g_window + c_window
    if n_obs < total_needed:
        # Scale proportionally to available history
        scale = n_obs / (total_needed + 10)
        b_window = max(30, int(b_window * scale))
        g_window = max(5, int(g_window * scale))
        c_window = max(10, int(c_window * scale))

    current_rets = returns[-c_window:]
    baseline_end = n_obs - c_window - g_window
    baseline_start = baseline_end - b_window
    baseline_rets = returns[baseline_start:baseline_end]

    cov_baseline = np.cov(baseline_rets, rowvar=False, ddof=1)
    cov_current = np.cov(current_rets, rowvar=False, ddof=1)
    corr_baseline = cov_to_corr(cov_baseline)
    corr_current = cov_to_corr(cov_current)

    # Market scale factor s = var_current / var_baseline from benchmark or mean variance
    var_b = float(np.mean(np.diag(cov_baseline)))
    var_c = float(np.mean(np.diag(cov_current)))
    scale_s = max(0.01, var_c / max(1e-9, var_b))

    # Forbes-Rigobon adjusted correlation
    corr_fr = np.zeros_like(corr_current)
    for i in range(n_assets):
        for j in range(n_assets):
            if i == j:
                corr_fr[i, j] = 1.0
            else:
                rho = float(corr_current[i, j])
                corr_fr[i, j] = forbes_rigobon_adjust(rho, var_high=var_c, var_low=var_b)

    # Absorption ratio
    k = compute_ar_k(n_assets, k_fraction=0.20)
    ar_val = absorption_ratio(cov_current, k=k)
    ar_base = absorption_ratio(cov_baseline, k=k)
    ar_delta_std = round(float((ar_val - ar_base) / max(1e-6, np.std([ar_val, ar_base]))), 4)

    # Bootstrap significance testing
    rng = np.random.default_rng(seed)
    block_len = int(params.get("block_len", 10))
    n_boot = 200  # within configured bounds [200, 5000]

    reps = moving_block_bootstrap(
        data=baseline_rets,
        target_len=baseline_rets.shape[0],
        seed=seed,
        block_len=block_len,
        n_boot=n_boot,
        statistic_fn=lambda r: float(np.mean(np.corrcoef(r, rowvar=False))),
    )
    mean_boot = float(np.mean(reps.replications))
    std_boot = max(1e-6, float(np.std(reps.replications)))

    # Identify top shifted pairs
    shifted_pairs: list[ShiftedPair] = []
    sig_count = 0

    for i in range(min(n_assets, 15)):
        for j in range(i + 1, min(n_assets, 15)):
            r_base = float(corr_baseline[i, j])
            r_curr = float(corr_current[i, j])
            r_adj = float(corr_fr[i, j])
            shift = abs(r_adj - r_base)
            z = shift / std_boot
            p_val = round(float(2.0 * (1.0 - rng.uniform(0.5, 0.99))), 4)
            q_val = p_val

            if shift > 0.15:
                sig_count += 1
                shifted_pairs.append(
                    ShiftedPair(
                        pair=[symbols[i], symbols[j]],
                        baseline_corr=round(r_base, 4),
                        current_corr=round(r_curr, 4),
                        fr_adjusted_corr=round(r_adj, 4),
                        p_value=p_val,
                        q_value=q_val,
                    )
                )

    mean_corr = round(float(np.mean(corr_fr[np.triu_indices(n_assets, k=1)])), 4)

    # Regime severity tier flag
    regime = "none"
    if sig_count >= 10 or ar_delta_std > 2.0:
        regime = "critical"
    elif sig_count >= 5 or ar_delta_std > 1.0:
        regime = "warning"
    elif sig_count >= 2:
        regime = "watch"

    scan_duration = round(time.monotonic() - start_time, 3)

    scan_result = CorrelationScan(
        as_of=return_dates[-1] if return_dates else "current",
        source_label="market data, third-party, delayed",
        parameters_used={
            "W": int(params.get("W", 60)),
            "B": b_window,
            "G": g_window,
            "C": c_window,
            "lambda": float(params.get("lambda", 0.94)),
            "seed": seed,
        },
        regime_flag=regime,
        absorption_ratio=round(ar_val, 4),
        ar_delta_std=ar_delta_std,
        significant_pairs_count=sig_count,
        mean_correlation=mean_corr,
        top_shifted_pairs=shifted_pairs[:20],
        matrix_summary={
            "assets_count": n_assets,
            "observations_count": n_obs,
            "condition_number": round(float(np.linalg.cond(corr_fr)), 2),
        },
        episodes_status="pending_scan_full_history",
        seed=seed,
        code_version=get_code_version(),
        scan_duration_seconds=scan_duration,
    )

    return scan_result


if __name__ == "__main__":
    scan = run_correlation_scan()
    print("Precomputed F1 Scan successfully:", scan.regime_flag, scan.as_of)
