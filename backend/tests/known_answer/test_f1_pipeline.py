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


def test_f1_news_search_executed_when_key_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backend skips no search when the search key is configured (Item 9)."""
    import backend.app.features.f1_contagion.pipeline as f1_pipe
    import backend.app.features.f1_contagion.explanation as f1_expl

    search_called = []

    def mock_fetch_tavily(query: str, settings=None, max_results: int = 5):
        search_called.append((query, max_results))
        return [
            {
                "title": "RBI Monetary Policy Stance Holds Stable",
                "url": "https://example.com/rbi-news",
                "content": "Monetary policy committee maintains rate.",
            }
        ]

    class MockSettings:
        def get_var_value(self, name: str):
            if name == "TAVILY_API_KEY":
                return "test-tavily-key-live"
            return None

    monkeypatch.setattr(f1_pipe, "load_settings", lambda: MockSettings())
    monkeypatch.setattr(f1_expl, "fetch_tavily_news", mock_fetch_tavily)
    monkeypatch.setattr(f1_pipe, "_CACHED_SCAN", None)

    scan = f1_pipe.run_correlation_scan()
    assert len(search_called) >= 1
    assert scan.news is not None
    assert scan.news.state == "results"
    assert len(scan.news.results) == 1
    assert scan.news.results[0].evidence_id == "E1"
    assert scan.news.results[0].title == "RBI Monetary Policy Stance Holds Stable"
    assert scan.hypotheses is not None


def test_f1_news_search_skipped_when_key_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backend returns not_run state when search key is unset (Item 9)."""
    import backend.app.features.f1_contagion.pipeline as f1_pipe

    class MockSettings:
        def get_var_value(self, name: str):
            return None

    monkeypatch.setattr(f1_pipe, "load_settings", lambda: MockSettings())
    monkeypatch.setattr(f1_pipe, "_CACHED_SCAN", None)

    scan = f1_pipe.run_correlation_scan()
    assert scan.news is not None
    assert scan.news.state == "not_run"
    assert scan.news.not_run_reason == "not run: no search key"




