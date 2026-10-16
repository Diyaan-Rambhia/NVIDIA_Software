"""Unit tests for Feature 1 pipeline and CorrelationScan contract."""

import json
from pathlib import Path

import pytest

from backend.app.contracts.contagion import CorrelationScan, ShiftedPair
from backend.app.features.f1_contagion.pipeline import (
    align_and_compute_returns,
    load_price_series,
)


def test_shifted_pair_contract() -> None:
    """Verify ShiftedPair contract validation and serialization."""
    pair = ShiftedPair(
        pair=["INFY.NS", "TCS.NS"],
        baseline_corr=0.45,
        current_corr=0.78,
        fr_adjusted_corr=0.65,
        p_value=0.012,
        q_value=0.024,
    )
    assert len(pair.pair) == 2
    assert pair.fr_adjusted_corr == 0.65
    dumped = pair.model_dump()
    assert dumped["pair"] == ["INFY.NS", "TCS.NS"]


def test_correlation_scan_contract_and_label() -> None:
    """Verify CorrelationScan requires the mandatory source label and parameters."""
    scan = CorrelationScan(
        as_of="latest_trading_day",
        source_label="unofficial source, demo only",
        parameters_used={"W": 60, "B": 250, "G": 20, "C": 20, "lambda": 0.94, "seed": 42},
        regime_flag="watch",
        absorption_ratio=0.72,
        ar_delta_std=1.2,
        significant_pairs_count=3,
        mean_correlation=0.35,
        top_shifted_pairs=[],
        matrix_summary={"assets_count": 50, "observations_count": 200},
        episodes_status="pending_scan_full_history",
        seed=42,
        code_version="v_test",
    )
    assert scan.source_label == "unofficial source, demo only"
    assert scan.parameters_used["seed"] == 42
    assert scan.episodes_status == "pending_scan_full_history"


def test_load_price_series_from_disk() -> None:
    """Ensure price series load correctly from cached local files."""
    series_map = load_price_series()
    assert isinstance(series_map, dict)
    assert len(series_map) >= 10
    first_sym = next(iter(series_map))
    assert len(series_map[first_sym]) >= 50


def test_align_and_compute_returns() -> None:
    """Verify alignment of price series and returns calculation."""
    series_map = load_price_series()
    symbols, rets, dates = align_and_compute_returns(series_map)
    assert len(symbols) >= 10
    assert rets.shape[1] == len(symbols)
    assert rets.shape[0] == len(dates)


def test_precomputed_f1_demo_file_exists() -> None:
    """Ensure data/f1_scan_demo.json was generated and adheres to contract."""
    fpath = Path("data") / "f1_scan_demo.json"
    assert fpath.exists(), "data/f1_scan_demo.json must exist"
    data = json.loads(fpath.read_text(encoding="utf-8"))
    scan = CorrelationScan.model_validate(data)
    assert scan.source_label == "unofficial source, demo only"
    assert scan.episodes_status == "pending_scan_full_history"
