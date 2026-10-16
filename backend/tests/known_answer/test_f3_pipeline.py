"""Known-answer and validation tests for Feature 3 pipeline."""

from datetime import date
from pathlib import Path

import pytest

from backend.app.contracts.portfolio import ColumnMapping
from backend.app.features.f3_log.pipeline import (
    build_portfolio_ledger,
    execute_feature3_review,
    load_benchmark_price_history,
    parse_trade_log_csv,
    replay_benchmark,
)


def test_parse_csv_explicit_mapping() -> None:
    csv_data = (
        "Date,Symbol,Side,Quantity,Price,Fees\n"
        "2025-01-10,INFY,BUY,10,1500.0,20.0\n"
        "2025-01-15,INFY,SELL,5,1600.0,10.0\n"
    )
    mapping = ColumnMapping(
        date="Date",
        symbol="Symbol",
        side="Side",
        quantity="Quantity",
        price="Price",
        fees="Fees",
    )
    log = parse_trade_log_csv(csv_data, mapping, consent_given=False)
    assert log.total_trades == 2
    assert log.symbols == ["INFY"]
    assert len(log.trades) == 2
    assert log.trades[0].quantity == 10.0
    assert log.trades[1].side == "SELL"


def test_parse_csv_row_numbered_errors() -> None:
    mapping = ColumnMapping(
        date="Date",
        symbol="Symbol",
        side="Side",
        quantity="Quantity",
        price="Price",
    )

    # Missing column header
    bad_header_csv = "Date,Symbol,Quantity,Price\n2025-01-10,INFY,10,1500.0\n"
    with pytest.raises(ValueError, match="Required column mapping for 'side'"):
        parse_trade_log_csv(bad_header_csv, mapping)

    # Row-numbered error for invalid side on line 2 (row index 2)
    bad_side_csv = "Date,Symbol,Side,Quantity,Price\n2025-01-10,INFY,HOLD,10,1500.0\n"
    with pytest.raises(ValueError, match="Row 2: invalid side 'HOLD'"):
        parse_trade_log_csv(bad_side_csv, mapping)

    # Row-numbered error for non-positive quantity on line 3 (row index 3)
    bad_qty_csv = (
        "Date,Symbol,Side,Quantity,Price\n"
        "2025-01-10,INFY,BUY,10,1500.0\n"
        "2025-01-15,INFY,BUY,-5,1500.0\n"
    )
    with pytest.raises(ValueError, match="Row 3: quantity must be strictly positive"):
        parse_trade_log_csv(bad_qty_csv, mapping)


def test_build_portfolio_ledger_fifo() -> None:
    csv_data = (
        "Date,Symbol,Side,Quantity,Price\n"
        "2025-01-01,TCS,BUY,10,3000.0\n"
        "2025-02-01,TCS,BUY,10,3200.0\n"
        "2025-03-01,TCS,SELL,15,3500.0\n"
    )
    mapping = ColumnMapping(
        date="Date",
        symbol="Symbol",
        side="Side",
        quantity="Quantity",
        price="Price",
    )
    log = parse_trade_log_csv(csv_data, mapping)
    portfolio, cash_flows, gain_events, loss_events = build_portfolio_ledger(
        log, latest_prices={"TCS": 3600.0}
    )

    # FIFO matching:
    # 10 sold against first lot @ 3000 -> gain = (3500 - 3000) * 10 = 5000
    # 5 sold against second lot @ 3200 -> gain = (3500 - 3200) * 5 = 1500
    # Total realized PnL = 6500
    assert portfolio.total_realized_pnl == 6500.0
    assert len(portfolio.positions) == 1
    pos = portfolio.positions[0]
    assert pos.quantity == 5.0
    assert pos.average_buy_price == 3200.0
    assert pos.current_value == 18000.0
    assert pos.unrealized_pnl == (3600.0 - 3200.0) * 5.0
    assert len(gain_events) == 2
    assert len(loss_events) == 0


def test_load_benchmark_and_missing_benchmark() -> None:
    # Test valid index from data/yfinance/
    nsei_prices = load_benchmark_price_history("NSEI")
    assert len(nsei_prices) > 50

    # Missing benchmark raises explicitly
    with pytest.raises(ValueError, match="Missing benchmark price data"):
        load_benchmark_price_history("NON_EXISTENT_INDEX")


def test_replay_benchmark_cash_flows() -> None:
    nsei_prices = load_benchmark_price_history("NSEI")
    dates = sorted(nsei_prices.keys())
    d1 = date.fromisoformat(dates[10])
    d2 = date.fromisoformat(dates[30])

    flows = [(d1, -10000.0), (d2, 10000.0)]
    replay = replay_benchmark(
        cash_flows=flows,
        benchmark_prices=nsei_prices,
        benchmark_name="NIFTY 50",
        xirr_bracket=(-0.99, 10.0),
        xirr_tol=1e-6,
        xirr_max_iter=200,
        xirr_grid_points=500,
    )
    assert replay.benchmark_name == "NIFTY 50"
    assert replay.terminal_value > 0.0


def test_execute_feature3_review_end_to_end() -> None:
    nsei_prices = load_benchmark_price_history("NSEI")
    dates = sorted(nsei_prices.keys())
    d1 = dates[5]
    d2 = dates[25]

    csv_data = (
        f"Date,Symbol,Side,Quantity,Price\n{d1},INFY,BUY,10,1400.0\n{d2},INFY,SELL,5,1500.0\n"
    )
    mapping = ColumnMapping(
        date="Date",
        symbol="Symbol",
        side="Side",
        quantity="Quantity",
        price="Price",
    )
    trade_log = parse_trade_log_csv(csv_data, mapping)
    review = execute_feature3_review(trade_log, is_institutional=True)

    assert review.portfolio is not None
    assert len(review.benchmark_replays) >= 1
    assert review.benchmark_replays[0].benchmark_name == "NIFTY 50"
    assert review.process_metrics.concentration_hhi > 0.0
    assert review.institutional_metrics is not None
    assert "LLM review not enabled" in review.review_text


def test_raw_log_consent_flag_storage_behavior(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Raw trade logs are stored only when consent_given is True; default off."""
    from backend.app.features.f3_log import pipeline

    test_logs_dir = tmp_path / "private_logs"
    monkeypatch.setattr(pipeline, "PRIVATE_LOGS_DIR", test_logs_dir)

    nsei_prices = load_benchmark_price_history("NSEI")
    dates = sorted(nsei_prices.keys())
    d0 = dates[0]

    csv_data = f"Date,Symbol,Side,Quantity,Price\n{d0},INFY,BUY,10,1400.0\n"
    mapping = ColumnMapping(
        date="Date",
        symbol="Symbol",
        side="Side",
        quantity="Quantity",
        price="Price",
    )

    # Consent False: nothing stored
    log_no_consent = parse_trade_log_csv(csv_data, mapping, consent_given=False)
    assert log_no_consent.consent_given is False
    assert log_no_consent.is_retained is False
    assert not test_logs_dir.exists() or len(list(test_logs_dir.glob("*.csv"))) == 0

    # Consent True: stored in private directory
    log_consent = parse_trade_log_csv(csv_data, mapping, consent_given=True)
    assert log_consent.consent_given is True
    assert log_consent.is_retained is True
    retained_files = list(test_logs_dir.glob("retained_trade_log_*.csv"))
    assert len(retained_files) == 1
    assert retained_files[0].read_text(encoding="utf-8") == csv_data


def test_empty_or_missing_trade_log_raises() -> None:
    """Missing or empty trade log raises a clear ValueError, never zeros."""
    mapping = ColumnMapping(
        date="Date",
        symbol="Symbol",
        side="Side",
        quantity="Quantity",
        price="Price",
    )

    with pytest.raises(ValueError, match="Missing trade log: trade log CSV content is empty"):
        parse_trade_log_csv("", mapping)

    with pytest.raises(ValueError, match="Missing trade log: trade log CSV content is empty"):
        parse_trade_log_csv("   \n\n  ", mapping)


def test_missing_risk_free_value_raises() -> None:
    """Missing risk-free rate in configuration raises ParameterError."""
    from backend.app.config.loader import ParameterError, load_config_file
    from backend.app.config.models import ParametersConfig
    from backend.app.features.f3_log.institutional_metrics import resolve_risk_free_rate

    params_cfg = load_config_file(Path("config") / "parameters.yaml", ParametersConfig)
    # Simulate null risk-free rate
    params_cfg.risk_free.value = None

    with pytest.raises(ParameterError, match="Risk-free rate is null"):
        resolve_risk_free_rate(params_cfg)


def test_synthetic_log_marker_detected() -> None:
    """Synthetic demo log marker is detected and recorded on TradeLog."""
    synthetic_file = Path("private") / "logs" / "demo_synthetic_log.csv"
    assert synthetic_file.is_file(), "Demo synthetic log must exist on disk"
    csv_text = synthetic_file.read_text(encoding="utf-8")

    mapping = ColumnMapping(
        date="Date",
        symbol="Symbol",
        side="Side",
        quantity="Quantity",
        price="Price",
        marker="Marker",
    )
    log = parse_trade_log_csv(csv_text, mapping, consent_given=False)
    assert log.is_synthetic_demo is True
    assert log.synthetic_marker == "SYNTHETIC_DEMO"
    assert log.total_trades > 0


def test_synthetic_log_labels_present_in_result() -> None:
    """Synthetic demo log produces explicit disclosure labels in DecisionReview and ProcessMetrics."""
    synthetic_file = Path("private") / "logs" / "demo_synthetic_log.csv"
    csv_text = synthetic_file.read_text(encoding="utf-8")
    mapping = ColumnMapping(
        date="Date",
        symbol="Symbol",
        side="Side",
        quantity="Quantity",
        price="Price",
        marker="Marker",
    )
    trade_log = parse_trade_log_csv(csv_text, mapping, consent_given=False)
    review = execute_feature3_review(trade_log)

    assert review.is_synthetic_demo is True
    assert review.synthetic_label == "SYNTHETIC DEMO LOG, not a real investor"
    assert review.process_metrics.process_label == "describes the generator, not a real investor"
    assert "SYNTHETIC DEMO LOG, not a real investor" in review.review_text


def test_synthetic_log_rejected_under_real_consent_flag() -> None:
    """Synthetic demo log is rejected if consent_given is True; never stored as real."""
    synthetic_file = Path("private") / "logs" / "demo_synthetic_log.csv"
    csv_text = synthetic_file.read_text(encoding="utf-8")
    mapping = ColumnMapping(
        date="Date",
        symbol="Symbol",
        side="Side",
        quantity="Quantity",
        price="Price",
        marker="Marker",
    )
    with pytest.raises(
        ValueError,
        match="Synthetic demo trade log cannot be accepted with real-log retention consent flag",
    ):
        parse_trade_log_csv(csv_text, mapping, consent_given=True)


def test_synthetic_log_missing_price_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing price series or date raises ValueError during synthetic log generation."""
    from scripts import make_demo_trade_log

    monkeypatch.setattr(make_demo_trade_log, "load_symbol_prices", lambda: {})
    with pytest.raises(ValueError, match="No stored price series found"):
        make_demo_trade_log.generate_synthetic_log(num_trades=5)


def test_synthetic_log_same_seed_gives_same_file(tmp_path: Path) -> None:
    """Synthetic demo log generator with identical seed outputs byte-for-byte identical files."""
    from scripts.make_demo_trade_log import generate_synthetic_log

    f1 = tmp_path / "run1.csv"
    f2 = tmp_path / "run2.csv"
    generate_synthetic_log(output_path=f1, seed=99, num_trades=5)
    generate_synthetic_log(output_path=f2, seed=99, num_trades=5)

    assert f1.read_bytes() == f2.read_bytes()
